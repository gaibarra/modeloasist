"""Repair only the 15 accidental accounts from ASIST_140926.xlsx.

Default is read-only preview. --apply takes a full backup and commits one
transaction. --verify checks the saved receipt without modifying database data.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.core.config import get_settings
from app.db.session import engine
from app.services.semester_file_import import normalized

BATCH = "50dfd4da-6e12-49c8-851b-c9c8cdedf85c"
REFERENCES = """select n.nspname,t.relname,a.attname from pg_constraint k
join pg_class t on t.oid=k.conrelid join pg_namespace n on n.oid=t.relnamespace
join pg_attribute a on a.attrelid=k.conrelid and a.attnum=any(k.conkey)
where k.contype='f' and k.confrelid='public.employees'::regclass"""


def pairs(connection):
    batch = connection.execute(text("select auto_created_employees from attendance_import_batches where id=:id"), {"id": BATCH}).scalar_one()
    people = [dict(r) for r in connection.execute(text("select * from employees")).mappings()]
    index = {e["id"]: e for e in people}
    result = []
    for created in batch:
        duplicate = index[int(created["employee_id"])]
        incoming = normalized(duplicate["nombre"])
        matches = []
        for original in people:
            name = normalized(original["nombre"])
            if (original["id"] != duplicate["id"] and incoming.startswith(name + " ")
                    and name.startswith(incoming[len(name) + 1:] + " ")
                    and original["departamento"] == duplicate["departamento"]
                    and original["external_employee_id"] == duplicate["id"]):
                matches.append(original)
        assert len(matches) == 1, f"Unsafe match: {duplicate['id']}"
        assert duplicate["email"] == f"emp-{duplicate['id']}@pendiente.local"
        assert duplicate["nombre"] == created["nombre"]
        result.append({"duplicate": duplicate, "original": matches[0]})
    assert len(result) == 15 and len({p["original"]["id"] for p in result}) == 15
    return result


def inspect(connection, plan):
    for pair in plan:
        params = {"old": pair["duplicate"]["id"], "new": pair["original"]["id"]}
        for schema, table, column in connection.execute(text(REFERENCES)):
            q = connection.dialect.identifier_preparer.quote
            count = connection.execute(text(f"select count(*) from {q(schema)}.{q(table)} where {q(column)}=:old"), params).scalar_one()
            assert not count or table in {"attendance_events", "employee_credentials", "employee_departments"}, f"Unexpected reference: {table}"
        pair["events"] = [dict(r) for r in connection.execute(text("select * from attendance_events where employee_id=:old order by id"), params).mappings()]
        pair["links"] = [dict(r) for r in connection.execute(text("select * from employee_departments where employee_id=:old"), params).mappings()]
        pair["original_count"] = connection.execute(text("select count(*) from attendance_events where employee_id=:new"), params).scalar_one()
        collisions = connection.execute(text("""select count(*) from attendance_events a join attendance_events b
            on a.event_ts=b.event_ts and coalesce(a.device_serial,'')=coalesce(b.device_serial,'')
            where a.employee_id=:old and b.employee_id=:new"""), params).scalar_one()
        assert collisions == 0, "Duplicate biometric events need explicit review"


def verify(connection, plan):
    for pair in plan:
        old, new = pair["duplicate"]["id"], pair["original"]["id"]
        assert connection.execute(text("select count(*) from employees where id=:id"), {"id": old}).scalar_one() == 0
        original = dict(connection.execute(text("select * from employees where id=:id"), {"id": new}).mappings().one())
        assert original == pair["original"]
        for event in pair["events"]:
            current = dict(connection.execute(text("select * from attendance_events where id=:id"), {"id": event["id"]}).mappings().one())
            expected = dict(event, employee_id=new)
            assert json.dumps(current, default=str, sort_keys=True) == json.dumps(expected, default=str, sort_keys=True)
        assert connection.execute(text("select count(*) from attendance_events where employee_id=:id"), {"id": new}).scalar_one() >= pair["original_count"] + len(pair["events"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = args.output / "consolidacion-15.json"
    if args.verify:
        plan = json.loads(receipt.read_text())["pairs"]
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            verify(connection, plan)
        print("Verified: 15 accounts consolidated; 29 events preserved with original IDs and timestamps.")
        return
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        plan = pairs(connection)
        inspect(connection, plan)
    print(json.dumps({"accounts": len(plan), "events": sum(len(p["events"]) for p in plan)}))
    if not args.apply:
        return
    assert not receipt.exists(), "Repair receipt exists; use --verify"
    url = make_url(get_settings().database_url)
    env = os.environ.copy()
    env["PGPASSWORD"] = url.password or ""
    backup = args.output / ("asistencia-antes-consolidacion-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + ".dump")
    subprocess.run(["pg_dump", "--host", url.host or "localhost", "--port", str(url.port or 5432), "--username", url.username,
                    "--dbname", url.database, "--format=custom", "--file", str(backup)], env=env, check=True)
    backup.chmod(0o600)
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout='10s'"))
        connection.execute(text("LOCK TABLE employees, attendance_events IN SHARE ROW EXCLUSIVE MODE"))
        plan = pairs(connection)
        inspect(connection, plan)
        recovery = {"batch_id": BATCH, "backup": str(backup), "pairs": plan}
        snapshot = args.output / "respaldo-consolidacion-15.json"
        with snapshot.open("x") as handle:
            json.dump(recovery, handle, ensure_ascii=False, indent=2, default=str)
        snapshot.chmod(0o600)
        for pair in plan:
            params = {"old": pair["duplicate"]["id"], "new": pair["original"]["id"]}
            connection.execute(text("update attendance_events set employee_id=:new where employee_id=:old"), params)
            # Preserve any department assignment not already present on the original.
            connection.execute(text("""insert into employee_departments (employee_id,department_id,is_primary,created_at)
                select :new,department_id,is_primary,created_at from employee_departments where employee_id=:old
                on conflict (employee_id,department_id) do nothing"""), params)
            connection.execute(text("delete from employee_departments where employee_id=:old"), params)
            connection.execute(text("delete from employee_credentials where employee_id=:old"), params)
            assert connection.execute(text("delete from employees where id=:old"), params).rowcount == 1
        verify(connection, plan)
    recovery["committed_at_utc"] = datetime.now(timezone.utc).isoformat()
    with receipt.open("x") as handle:
        json.dump(recovery, handle, ensure_ascii=False, indent=2, default=str)
    receipt.chmod(0o600)
    print("Committed: 15 duplicate accounts removed, 29 attendance events reassigned; original names preserved.")


if __name__ == "__main__":
    main()
