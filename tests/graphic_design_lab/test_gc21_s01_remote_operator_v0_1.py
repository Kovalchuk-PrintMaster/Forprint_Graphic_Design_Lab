"""Offline tests: operator single-use boundaries; no SSH/Windows execution."""
from pathlib import Path
import importlib.util
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import tempfile
import unittest

def source_file(name):
    here=Path(__file__).resolve().parent
    return (here / name) if (here / name).exists() else (here.parents[1] / 'scripts/graphic_design_lab/worker_runtime' / name)

SOURCE = source_file('gc21_s01_remote_operator_v0_1.py')
spec = importlib.util.spec_from_file_location('gc21_s01_remote_operator_v0_1', SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class GC21RemoteOperatorTest(unittest.TestCase):
    def test_ssh_is_pinned(self):
        opts=mod.ssh_options()
        self.assertIn('StrictHostKeyChecking=yes', opts)
        self.assertIn('BatchMode=yes', opts)
        self.assertIn('ConnectTimeout=10', opts)
        self.assertEqual(mod.HOST, 'work@192.168.50.69')

    def test_remote_powershell_encoded_unicode(self):
        import base64
        ps='Write-Output "Привіт"'
        arg=mod.ps_command(ps)
        self.assertEqual(base64.b64decode(arg[-1]).decode('utf-16le'), ps)
        self.assertIn('-NonInteractive', arg)

    def test_one_attempt_paths(self):
        self.assertIn('jobs\\gdl-gc21-card-001\\a0001', mod.JOB)
        self.assertEqual(mod.REMOTE_ZIP, 'gc21_remote_executor_v0_1.zip')

    def test_bundle_missing_fail_closed(self):
        with self.assertRaises(ValueError):
            mod.verify_local_bundle(Path('/file/not/present.zip'))

    def test_bundle_wrong_filename_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'wrong.zip'
            p.write_bytes(b'NO')
            with self.assertRaises(ValueError):
                mod.verify_local_bundle(p)

    def test_bundle_digest_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/mod.EXPECTED_ZIP_NAME
            m={'schema':'gdl_gc21_remote_single_use_bundle_v0_1','files_sha256':{mod.RUNNER:'0'*64,mod.CONTROL:'1'*64}}
            with ZipFile(p,'w',ZIP_DEFLATED) as z:
                z.writestr(mod.RUNNER,'defective')
                z.writestr(mod.CONTROL,'defective')
                z.writestr('bundle_manifest.json',json.dumps(m))
                z.writestr('00_README_UA.md','test')
            with self.assertRaisesRegex(ValueError,'BUNDLE_FILE_HASH_MISMATCH'):
                mod.verify_local_bundle(p)

    def test_windows_script_no_legacy_task(self):
        ctrl=source_file(mod.CONTROL).read_text()
        runner=source_file(mod.RUNNER).read_text()
        self.assertIn('ForPrint-GDL-GC21-Card-001-A0001',ctrl)
        self.assertNotIn('gdl-w253-limited-native-001',ctrl+runner)
        self.assertIn('New-ScheduledTaskPrincipal',ctrl)
        self.assertIn('-LogonType Interactive -RunLevel Limited',ctrl)
        self.assertIn('GetActiveObject',runner)
        self.assertIn("[IO.FileMode]::CreateNew",runner)
        self.assertIn("Move-Item -LiteralPath $Partial -Destination $Final",runner)
        self.assertIn('gc21_launch_claim.json',ctrl+runner)
        self.assertNotIn('Remove-Item',ctrl+runner)

    def test_controller_runner_sha_binding(self):
        ctrl=source_file(mod.CONTROL).read_text()
        runner=source_file(mod.RUNNER).read_bytes()
        expected=hashlib.sha256(runner).hexdigest()
        self.assertIn("$ExpectedRunnerSha='"+expected+"'",ctrl)

if __name__=='__main__': unittest.main()
