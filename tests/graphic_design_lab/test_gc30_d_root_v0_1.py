from pathlib import Path
from hashlib import sha256
import importlib.util
import sys

ROOT=Path(__file__).resolve().parents[2]
W=ROOT/'scripts/graphic_design_lab/greeting_cards/windows/gc30_dedicated_worker_v0_1.ps1'
INSTALL=ROOT/'scripts/graphic_design_lab/greeting_cards/gc30_client_bootstrap_install_v0_1.py'

def test_runtime_restricted_to_existing_d_root():
    b=W.read_bytes(); assert b.startswith(b'\xef\xbb\xbf')
    s=b.decode('utf-8-sig')
    assert "$Base='D:\\ForPrint_Automation\\GraficsDesignLab\\Automation'" in s
    assert "Need (Dir $Base) 'GC30_GDL_D_ROOT_MISSING_OR_UNSAFE'" in s
    assert '$env:LOCALAPPDATA' not in s
    assert '$home=' not in s.lower()
    assert '$ClientHome=' in s

def test_root_pinned_by_registered_config():
    s=W.read_text('utf-8-sig')
    assert 'local_root=$Base' in s
    assert "GC30_RUNTIME_ROOT_DRIFT" in s
    assert "GC30_RUN_LOCAL_INSTALLED_WORKER_ONLY" in s
    assert "GC30_EXPLICIT_REGISTRATION_REQUIRED" in s
    assert "GC30_WORKER_ALREADY_INSTALLED" in s
    assert "GC30_LOCAL_JOB_ALREADY_EXISTS_RECONCILE" in s
    assert 'Start-Process' not in s

def test_client_installer_pin_matches_new_worker():
    source=INSTALL.read_text('utf-8')
    assert sha256(W.read_bytes()).hexdigest() in source
    assert "GC30_EXISTING_CLIENT_FILE_CONFLICT" in source

def test_nonproduction_and_one_stage():
    s=W.read_text('utf-8-sig')
    assert "production_ready=$false" in s
    assert "client_published=$false" in s
    assert "GC30_POLL_ONCE=STAGED_ONE_JOB" in s
    assert 'New-Object -ComObject' not in s
