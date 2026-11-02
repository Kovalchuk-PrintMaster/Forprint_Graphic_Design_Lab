#!/usr/bin/env python3
"""Installed GC47AX source-only regression tests. No Windows/native attempts."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
CAN=ROOT/'scripts/graphic_design_lab/greeting_cards'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):
    p=CAN/name
    spec=importlib.util.spec_from_file_location(name.replace('.py',''),p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class TestGC47AX(unittest.TestCase):
    def test_01_shadow_canonical(self):
        ar=load('gc47ax_versioned_native_pilot_r001.py')
        self.assertNotIn('tmp/',ar.SHADOW_REL)
        self.assertIn('coordination/',ar.SHADOW_REL)
    def test_02_as_new_ar_sha(self):
        a=load('gc47ax_illustrator_lifecycle_r001.py')
        self.assertEqual(a.AR_SHA,sha(CAN/a.AR_FILE))
    def test_03_postflight_as_sha(self):
        a=load('gc47ax_postflight_r001.py')
        self.assertEqual(a.AS_SHA,sha(CAN/a.AS_NAME))
        # Only the repository-relative lock location matters. The containing
        # server root (or disposable test fixture) can itself be named 'tmp'.
        self.assertEqual(a.LOCK,ROOT.parent/'.state/graphic_design_lab/lifecycle/gc47ax_single_lifecycle_r001.lock')
        self.assertFalse(a.LOCK.is_relative_to(ROOT/'tmp'))
    def test_04_ui_postflight_sha(self):
        a=load('gc47ax_client_windows_bridge_r001.py')
        self.assertEqual(a.POSTFLIGHT_SHA,sha(a.POSTFLIGHT))
        self.assertEqual(a.LIFECYCLE_SHA,sha(a.LIFECYCLE))
    def test_05_baseline_source_sha(self):
        a=load('gc47ax_versioned_native_pilot_r001.py')
        self.assertEqual(sha(ROOT/a.SHADOW_REL),a.SHADOW_SHA)
    def test_06_no_implicit_pilot(self):
        a=load('gc47ax_postflight_r001.py')
        with patch.object(a,'load_lifecycle',return_value=object()):
            self.assertEqual(a.main(['--mode','pilot','--client-name','test']),2)
    def test_07_no_unauthorized_profile(self):
        a=load('gc47ax_client_windows_bridge_r001.py')
        self.assertEqual(a.VERSIONED_JOB,'gdl_gc_zap_20261011')
    def test_08_no_ui_renderer(self):
        s=(CAN/'gc47ax_client_windows_bridge_r001.py').read_text('utf8')
        self.assertIn('BLOCKED_RENDERER_CAPABILITY_NOT_PROVEN',s)
    def test_09_status_only_other_profile(self):
        s=(CAN/'gc47ax_client_windows_bridge_r001.py').read_text('utf8')
        self.assertIn('BLOCKED_VERSIONED_PROFILE_NOT_YET_SUPPORTED_NO_DISPATCH',s)
    def test_10_lock_canonical_parent(self):
        a=load('gc47ax_postflight_r001.py')
        self.assertEqual(a.LOCK.parent.parent,ROOT.parent/'.state'/'graphic_design_lab')

if __name__=='__main__':unittest.main(verbosity=2)
