import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/redeploy_departamento_automatico.sh'


class FrontendDeployTests(unittest.TestCase):
    def test_syntax_and_invalid_mode(self):
        subprocess.run(['bash', '-n', str(SCRIPT)], check=True)
        result = subprocess.run(['bash', str(SCRIPT), '--invalid'], capture_output=True)
        self.assertEqual(result.returncode, 2)

    def test_exact_reviewed_files(self):
        source = SCRIPT.read_text()
        manifest = re.search(r"<<'SOURCE_HASHES'\n(.*?)\nSOURCE_HASHES", source, re.S)[1]
        expected = {'frontend/src/app/staff/page.tsx', 'frontend/src/components/auto-submit-select.tsx',
                    'frontend/tests/auto-submit-select.test.cjs'}
        paths = set()
        for line in manifest.splitlines():
            digest, path = line.split('  ')
            paths.add(path)
            self.assertEqual(hashlib.sha256((SCRIPT.parents[2] / path).read_bytes()).hexdigest(), digest)
        self.assertEqual(paths, expected)

    def test_only_frontend_and_no_data_operations(self):
        source = SCRIPT.read_text()
        self.assertNotIn('asistenciamodelo-backend', source)
        for command in ['alembic', 'psql', 'pg_restore', 'systemctl restart nginx']:
            self.assertNotIn(command, source)
        self.assertIn('20261026T142227Z-vacaciones/frontend', source)
        self.assertGreater('zzzzzzzzzzzzz-department-auto.conf', 'zzzzzzzzzzzz-vacaciones.conf')
        self.assertIn('tests/auto-submit-select.test.cjs', source)
        self.assertIn('cmp -s', source)

    def cleanup_case(self, finished=False, external=False):
        function = SCRIPT.read_text().split('cleanup() {', 1)[1].split('trap cleanup EXIT', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'new-frontend.conf').write_text('new')
            (root / 'override.conf').write_text('external' if external else 'new')
            (root / 'previous.conf').write_text('old')
            code = f'''
BACKUP='{root}'
DROP='{root}/override.conf'
SMOKE=''
SWITCHED=1
FINISHED={int(finished)}
UNIT=frontend
OLD=/old/frontend
systemctl() {{ if [[ "$1" == show ]]; then echo /old/frontend; else echo "MOCK $*"; fi; }}
wait_http() {{ return 0; }}
cleanup() {{{function}
true
cleanup
'''
            result = subprocess.run(['bash', '-s'], input=code, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0 if finished else 1)
            self.assertEqual((root / 'previous.conf').read_text(), 'old')
            self.assertEqual((root / 'override.conf').exists(), finished or external)
            self.assertEqual('MOCK restart frontend' in result.stdout, not (finished or external))

    def test_failure_reverts_frontend_only(self):
        self.cleanup_case()

    def test_success_keeps_override(self):
        self.cleanup_case(finished=True)

    def test_external_edit_is_preserved(self):
        self.cleanup_case(external=True)


if __name__ == '__main__':
    unittest.main()
