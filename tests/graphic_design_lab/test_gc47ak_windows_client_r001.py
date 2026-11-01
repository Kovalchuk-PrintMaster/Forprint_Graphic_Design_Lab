"""GC47AK offline tests; no SSH/Windows/Illustrator/SMB mutating calls."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards'
# In package staging, test path and sources are both under payload/.
HERE = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards'

def load(name):
    path = HERE / f'{name}.py'
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

bridge = load('gc47ak_windows_bridge_r001')
deploy = load('gc47ak_windows_client_deploy_r001')

class GC47AKTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='gc47ak_test_')
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.share = root/'data'
        self.share.mkdir()
        self.client='Виктория Беспалова _+380 67 793 00 15'
        self.ws=self.share/self.client/'_forprint_automation'
        for name in ('input','output','template_studio'):
            (self.ws/name).mkdir(parents=True,exist_ok=True)
        self.fakebridge=root/'bridge.py'
        self.fakebridge.write_text('# fixture',encoding='utf-8')
        self.patcher=mock.patch.object(deploy,'BRIDGE',self.fakebridge)
        self.patcher.start();self.addCleanup(self.patcher.stop)

    def test_01_unicode_token_roundtrip(self):
        self.assertEqual(bridge.decode_client(bridge.encode_client(self.client)),self.client)
    def test_02_token_ascii_only(self):
        self.assertRegex(bridge.encode_client(self.client),r'^[A-Za-z0-9_-]+$')
    def test_03_invalid_token_slash(self):
        with self.assertRaises(bridge.Blocked):bridge.decode_client('abcd/efgh')
    def test_04_invalid_token_equals(self):
        with self.assertRaises(bridge.Blocked):bridge.decode_client('abcd==')
    def test_05_invalid_utf8(self):
        with self.assertRaises(bridge.Blocked):bridge.decode_client(base64.urlsafe_b64encode(b'\xff\xfe').decode().rstrip('='))
    def test_06_invalid_bad_base64(self):
        with self.assertRaises(bridge.Blocked):bridge.decode_client('a')
    def test_07_reject_dotdot(self):
        with self.assertRaises(bridge.Blocked):bridge.encode_client('..')
    def test_08_reject_slash_in_client(self):
        with self.assertRaises(bridge.Blocked):bridge.encode_client('abc/def')
    def test_09_reject_backslash_in_client(self):
        with self.assertRaises(bridge.Blocked):bridge.encode_client('abc\\def')
    def test_10_reject_control_in_client(self):
        with self.assertRaises(bridge.Blocked):bridge.encode_client('ab\ncd')
    def test_11_reject_non_nfc(self):
        with self.assertRaises(bridge.Blocked):bridge.encode_client('e\u0301')
    def test_12_reject_long_client(self):
        with self.assertRaises(bridge.Blocked):bridge.encode_client('x'*151)
    def test_13_reject_noncanonical_token(self):
        # Canonical base64url-without-padding required.
        with self.assertRaises(bridge.Blocked):bridge.decode_client('eA==')
    def test_14_workspace_with_utf8_client(self):
        self.assertEqual(deploy.workspace(self.client,self.share),self.ws)
    def test_15_workspace_reject_other_depth(self):
        with self.assertRaises(deploy.Blocked):deploy.workspace('not-there',self.share)
    def test_16_workspace_reject_path(self):
        with self.assertRaises(deploy.Blocked):deploy.workspace('a/b',self.share)
    def test_17_workspace_reject_client_symlink(self):
        fake=self.share/'link';fake.symlink_to(self.share/self.client,target_is_directory=True)
        with self.assertRaises(deploy.Blocked):deploy.workspace('link',self.share)
    def test_18_ready_add_only(self):
        ws,old,missing=deploy.inspect(self.client,self.share)
        self.assertEqual(ws,self.ws)
        self.assertFalse(old);self.assertEqual(len(missing),3)
    def test_19_install_created_only_three(self):
        old=self.ws/'input'/'Створити_листівку.cmd';old.write_bytes(b'LEGACY')
        self.assertEqual(deploy.install(self.client,self.share),'INSTALLED_SIDE_BY_SIDE')
        self.assertEqual(old.read_bytes(),b'LEGACY')
        self.assertEqual({p.name for p in (self.ws/'input').iterdir()},
                         {old.name,deploy.CMD,deploy.PS1,deploy.HELP})
    def test_20_repeat_idempotent(self):
        self.assertEqual(deploy.install(self.client,self.share),'INSTALLED_SIDE_BY_SIDE')
        self.assertEqual(deploy.install(self.client,self.share),'ALREADY_INSTALLED')
    def test_21_guard_changed_existing_launcher(self):
        (self.ws/'input'/deploy.CMD).write_text('untrusted')
        with self.assertRaises(deploy.Blocked):deploy.install(self.client,self.share)
    def test_22_partial_install_denied(self):
        (self.ws/'input'/deploy.CMD).write_bytes(deploy.cmd_bytes())
        with self.assertRaises(deploy.Blocked):deploy.install(self.client,self.share)
    def test_23_nonexisting_bridge_denied(self):
        self.fakebridge.unlink()
        with self.assertRaises(deploy.Blocked):deploy.inspect(self.client,self.share)
    def test_24_utf8_cmd_and_powershell(self):
        self.assertIn(b'powershell.exe', deploy.cmd_bytes())
        self.assertTrue(deploy.ps1_bytes().startswith(b'\xef\xbb\xbf'))
    def test_25_cmd_not_old_gc30(self):
        content=deploy.cmd_bytes().decode('utf-8')
        self.assertNotIn('gc30_submit_only',content)
        self.assertNotIn('gdl_greeting_card_illustrator_native',content)
    def test_26_ps1_strict_unc(self):
        text=deploy.ps1_bytes().decode('utf-8-sig')
        self.assertIn('GC47AK_ORIGINAL_CLIENT_UNC_REQUIRED',text)
        self.assertIn('In_Progress',text)
        self.assertIn('_forprint_automation',text)
        self.assertIn('ReparsePoint',text)
    def test_27_ps1_interactive_live_tty(self):
        text=deploy.ps1_bytes().decode('utf-8-sig')
        self.assertIn(' -tt ',text)
        self.assertIn('& $ssh.Source',text)
        self.assertNotIn('2>&1 |',text)
    def test_28_ps1_no_exfil_or_password(self):
        text=deploy.ps1_bytes().decode('utf-8-sig')
        self.assertNotIn('Invoke-Expression',text)
        self.assertNotIn('ConvertTo-SecureString',text)
        self.assertNotIn('password=',text.lower())
    def test_29_ps1_remote_only_bridge(self):
        text=deploy.ps1_bytes().decode('utf-8-sig')
        self.assertIn('gc47ak_windows_bridge_r001.py',text)
        self.assertNotIn('forprint_prepress_hub',text)
        self.assertNotIn('gc29_native_four_page',text)
    def test_30_no_automatic_retry(self):
        ps=deploy.ps1_bytes().decode('utf-8-sig')
        self.assertEqual(ps.count('& $ssh.Source'),1)
        self.assertIn('GC47AK_SSH_OR_REMOTE_EXIT_',ps)
    def test_31_remote_mode_restrict(self):
        self.assertIn("choices=('check', 'sources', 'attempts', 'interactive')",(HERE/'gc47ak_windows_bridge_r001.py').read_text())
    def test_32_bridge_pinned_ui(self):
        self.assertRegex(bridge.UI_SHA256,r'^[a-f0-9]{64}$')
        self.assertIn('GC47AJ_SOURCE_NOT_PINNED',(HERE/'gc47ak_windows_bridge_r001.py').read_text())
    def test_33_bridge_denies_fake_unsafe_token_without_ui_load(self):
        with mock.patch.object(bridge,'load_ui',side_effect=AssertionError('unsafe import')):
            with self.assertRaises(bridge.Blocked):bridge.execute('interactive','_oops!')
    def test_34_bridge_check_no_native_dispatch(self):
        ai=object()
        ui=object()
        with mock.patch.object(bridge,'load_ui',return_value=ui),mock.patch.object(bridge,'bound_context',return_value=(ai,self.ws)):
            self.assertEqual(bridge.execute('check',bridge.encode_client(self.client)),0)
    def test_35_bridge_interactive_single_delegation(self):
        calls=[]
        class FakeUI:
            def interactive(self,ai,client,ws):
                calls.append((ai,client,ws));return 0
        ai=object()
        with mock.patch.object(bridge,'load_ui',return_value=FakeUI()),mock.patch.object(bridge,'bound_context',return_value=(ai,self.ws)):
            self.assertEqual(bridge.execute('interactive',bridge.encode_client(self.client)),0)
        self.assertEqual(calls,[(ai,self.client,self.ws)])
    def test_36_bridge_production_not_authorized(self):
        text=(HERE/'gc47ak_windows_bridge_r001.py').read_text()
        self.assertIn('PRODUCTION_READY=FALSE',text)
        self.assertNotIn('os.system',text)
        self.assertNotIn('shell=True',text)
    def test_37_shell_wrapper_bytes_stable(self):
        self.assertEqual(deploy.cmd_bytes(),deploy.cmd_bytes())
        self.assertEqual(deploy.ps1_bytes(),deploy.ps1_bytes())
    def test_38_no_writes_during_inspect(self):
        before=set(self.ws.joinpath('input').iterdir())
        deploy.inspect(self.client,self.share)
        self.assertEqual(before,set(self.ws.joinpath('input').iterdir()))

if __name__=='__main__':unittest.main(verbosity=2)
