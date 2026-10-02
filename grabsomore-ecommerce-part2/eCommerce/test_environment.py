"""Verify .env discovery and process-environment precedence in isolation."""

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from django.test import SimpleTestCase


class EnvironmentLoadingTests(SimpleTestCase):
    """Load a copied settings module without changing the project's real .env."""

    def test_dotenv_loads_beside_manage_py_and_preserves_exported_values(self):
        """Find the project file from any working directory without overriding CI."""
        original = Path(__file__).resolve().parent.parent / 'AuthLog/settings.py'
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'AuthLog').mkdir()
            settings = root / 'AuthLog/settings.py'
            settings.write_text(original.read_text())
            (root / '.env').write_text('DB_ENGINE=sqlite\nDJANGO_DEBUG=0\nDJANGO_ALLOWED_HOSTS=example.test\nDEFAULT_FROM_EMAIL=dotenv@example.test\n')
            environment = {key: value for key, value in os.environ.items() if key not in ('DJANGO_DEBUG', 'DJANGO_ALLOWED_HOSTS', 'DEFAULT_FROM_EMAIL', 'DB_ENGINE', 'PYTHON_DOTENV_DISABLED')}
            script = "import runpy,json,sys; s=runpy.run_path(sys.argv[1]); print(json.dumps([s['DEBUG'],s['ALLOWED_HOSTS'],s['DEFAULT_FROM_EMAIL']]))"
            result = subprocess.run([sys.executable, '-c', script, str(settings)], cwd=root/'AuthLog', env=environment, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout), [False, ['example.test'], 'dotenv@example.test'])
            environment['DJANGO_DEBUG'] = '1'
            result = subprocess.run([sys.executable, '-c', script, str(settings)], cwd=root/'AuthLog', env=environment, check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(result.stdout)[0])
