"""Local rollback tests with mocked systemctl; never talks to real services."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/redeploy_colaboradores.sh"


class DeployScriptTests(unittest.TestCase):
    def test_shell_and_embedded_python_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        blocks = re.findall(r"<<'PY'\n(.*?)\nPY", SCRIPT.read_text(), re.S)
        self.assertGreaterEqual(len(blocks), 3)
        for block in blocks:
            compile(block, "embedded-python", "exec")

    def test_operator_rollback_shell_syntax(self):
        source = SCRIPT.read_text()
        rollback = source.split('cat > "$BACKUP/rollback.sh" <<EOF\n', 1)[1].split('\nEOF', 1)[0]
        result = subprocess.run(['bash', '-n'], input=rollback.replace('\\$', '$'), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_mode_exits_before_any_action(self):
        result = subprocess.run(["bash", str(SCRIPT), "--invalid"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Uso:", result.stderr)

    def test_pinned_commit_and_campus_checks(self):
        source = SCRIPT.read_text()
        self.assertIn("25f5cb0fac455373dd4d650221269642727c59db^{commit}", source)
        self.assertIn('git_repo archive "$COMMIT"', source)
        self.assertNotIn('git_repo rev-parse HEAD', source)
        self.assertIn('tests/test_campus_hours.py', source)
        self.assertIn('zzzz-release-colaboradores.conf', source)
        self.assertIn('/opt/asistenciamodelo/releases/*', source)
        self.assertIn('tests/test_employee_management.py tests/test_auth.py', source)
        self.assertIn('13101/colaboradores 307', source)
        self.assertIn('18184/employees/manage 401', source)
        self.assertIn('online/api/colaboradores 401', source)
        self.assertIn('13101/api/staff/campus-hours 401', source)
        self.assertIn('online/api/staff/campus-hours 401', source)
        self.assertNotIn('alembic upgrade', source)
        self.assertNotIn('systemctl restart nginx', source)

    def run_cleanup(self, frontend_exists=True, finished=False, external_edit=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "new-backend.conf").write_text("new-backend")
            (root / "new-frontend.conf").write_text("new-frontend")
            (root / "backend.conf").write_text("external-change" if external_edit else "new-backend")
            if frontend_exists:
                (root / "frontend.conf").write_text("new-frontend")
            (root / "old-override.conf").write_text("original-ccc6b72")
            function = SCRIPT.read_text().split("cleanup() {", 1)[1].split("trap cleanup EXIT", 1)[0]
            source = f'''
BACKUP='{root}'
BACK_DROP='{root}/backend.conf'
FRONT_DROP='{root}/frontend.conf'
OLD_BACK=/old/backend
OLD_FRONT=/old/frontend
BACKEND=backend
FRONTEND=frontend
SMOKE_BACK=''
SMOKE_FRONT=''
SWITCHED=1
FINISHED={int(finished)}
systemctl() {{
  if [[ "$1" == show ]]; then
    if [[ "$2" == backend ]]; then echo /old/backend; else echo /old/frontend; fi
  else
    echo "MOCK $*"
  fi
}}
wait_http() {{ return 0; }}
cleanup() {{{function}
true
cleanup
'''
            result = subprocess.run(["bash", "-s"], input=source, text=True, capture_output=True)
            self.assertEqual((root / "old-override.conf").read_text(), "original-ccc6b72")
            if finished or external_edit:
                self.assertTrue((root / "backend.conf").exists())
                self.assertNotIn("MOCK restart", result.stdout)
            else:
                self.assertFalse((root / "backend.conf").exists())
                self.assertFalse((root / "frontend.conf").exists())
                self.assertTrue((root / "failed-backend-override.conf").exists())
                self.assertIn("MOCK restart backend", result.stdout)
                self.assertIn("MOCK restart frontend", result.stdout)
            self.assertEqual(result.returncode, 0 if finished else 1, result.stderr)

    def test_failure_restores_previous_overrides(self):
        self.run_cleanup()

    def test_failure_before_frontend_switch(self):
        self.run_cleanup(frontend_exists=False)

    def test_success_never_rolls_back(self):
        self.run_cleanup(finished=True)

    def test_external_override_edits_are_preserved(self):
        self.run_cleanup(external_edit=True)


if __name__ == "__main__":
    unittest.main()
