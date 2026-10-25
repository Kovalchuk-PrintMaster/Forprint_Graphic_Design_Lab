"""GC26 native client launcher installer; synthetic SMB tree and client files only."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from hashlib import sha256
import sys
import pytest

THIS = Path(__file__).resolve()
MODULE = THIS.parents[2]/'scripts/graphic_design_lab/greeting_cards/gc26_illustrator_client_launcher_deploy_v0_1.py'
spec = importlib.util.spec_from_file_location('gc26_installer_test', MODULE)
f = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = f
spec.loader.exec_module(f)

@pytest.fixture
def sample(tmp_path, monkeypatch):
    repo=tmp_path/'repo'
    path=repo/'scripts/graphic_design_lab/greeting_cards/windows'
    path.mkdir(parents=True)
    (path/'gdl_greeting_card_illustrator_check_v0_1.ps1').write_bytes(
        b'# forprint_graphic_design_lab gc25-illustrator-queue-check '+b'a'*130)
    (path/'launch_greeting_card_illustrator_check_v0_1.cmd').write_bytes(
        b'# gdl_greeting_card_illustrator_check_v0_1.ps1 '+b'b'*130)
    monkeypatch.setattr(f, 'PINNED_LAUNCHER_SHA256', {
        item.name: sha256((repo/item).read_bytes()).hexdigest() for item in map(Path, f.SOURCES)
    })
    share=tmp_path/'share';share.mkdir()
    folder=share/'Клієнт №1'/'_forprint_automation'
    (folder/'input').mkdir(parents=True);(folder/'output').mkdir()
    (folder/'input'/'launch_greeting_card_queue.cmd').write_bytes(b'LEGACY_PDF_COMMAND')
    (folder/'input'/'accepted.zip').write_bytes(b'UNCHANGED_JOB_ZIP')
    return repo,share,folder


def test_sources_exact_two(sample):
    repo,_,_=sample
    assert set(f.sources(repo))==set(Path(x).name for x in f.SOURCES)


def test_workspace_unicode_and_one_level(sample):
    _,share,folder=sample
    assert f.client_workspace('Клієнт №1', share)==folder
    with pytest.raises(f.Blocked):f.client_workspace('Клієнт №1/../../bad', share)
    with pytest.raises(f.Blocked):f.client_workspace('../bad', share)


def test_missing_workspace_refused(sample):
    _,share,_=sample
    with pytest.raises(f.Blocked,match='CLIENT_WORKSPACE_MISSING_OR_SYMLINK'):
        f.client_workspace('no-such-client',share)


def test_symlink_client_refused(sample):
    _,share,folder=sample
    (share/'alias').symlink_to(folder.parent, target_is_directory=True)
    with pytest.raises(f.Blocked):f.client_workspace('alias',share)


def test_discover_read_only(sample,capsys):
    _,share,folder=sample
    before=[(p.name,p.read_bytes()) for p in (folder/'input').iterdir()]
    n,_=f.discover(share)
    assert n==1 and 'INPUT_ZIPS=1' in capsys.readouterr().out
    assert before==[(p.name,p.read_bytes()) for p in (folder/'input').iterdir()]


def test_check_read_only(sample):
    repo,_,folder=sample
    data=f.sources(repo)
    assert set(f.audit(folder,data).values())=={'MISSING'}
    assert sorted(p.name for p in (folder/'input').iterdir())==['accepted.zip','launch_greeting_card_queue.cmd']


def test_install_requires_confirmation(sample):
    repo,_,folder=sample
    with pytest.raises(f.Blocked,match='EXPLICIT_INSTALL_CONFIRMATION_REQUIRED'):
        f.deploy(folder,f.sources(repo),confirm=False)


def test_install_exact_two_without_source_mutation(sample):
    repo,_,folder=sample
    originals={p.name:p.read_bytes() for p in (folder/'input').iterdir()}
    result=f.deploy(folder,f.sources(repo),confirm=True)
    assert set(result.values())=={'INSTALLED'}
    assert set(f.audit(folder,f.sources(repo)).values())=={'CURRENT'}
    for name,data in originals.items():
        assert (folder/'input'/name).read_bytes()==data


def test_idempotent_existing_identical_files(sample):
    repo,_,folder=sample;data=f.sources(repo)
    f.deploy(folder,data,confirm=True)
    assert set(f.deploy(folder,data,confirm=True).values())=={'CURRENT'}


def test_collision_blocks_before_any_copy(sample):
    repo,_,folder=sample;data=f.sources(repo)
    target=folder/'input'/'launch_greeting_card_illustrator_check_v0_1.cmd'
    target.write_bytes(b'CUSTOMER_EXISTING_LAUNCHER')
    with pytest.raises(f.Blocked,match='EXISTING_CLIENT_LAUNCHER_DIFFERS_NO_OVERWRITE'):
        f.deploy(folder,data,confirm=True)
    assert target.read_bytes()==b'CUSTOMER_EXISTING_LAUNCHER'
    assert not (folder/'input'/'gdl_greeting_card_illustrator_check_v0_1.ps1').exists()


def test_collision_with_symlink_refused(sample,tmp_path):
    repo,_,folder=sample
    target=folder/'input'/'gdl_greeting_card_illustrator_check_v0_1.ps1'
    victim=tmp_path/'victim';victim.write_text('DO_NOT_TOUCH')
    target.symlink_to(victim)
    with pytest.raises(f.Blocked,match='CLIENT_LAUNCHER_SYMLINK_FORBIDDEN'):
        f.deploy(folder,f.sources(repo),confirm=True)
    assert victim.read_text()=='DO_NOT_TOUCH'


def test_bad_source_route_fails_closed(sample):
    repo,_,_=sample
    p=repo/f.SOURCES[0]
    p.write_bytes(b'WRONG_BRANCH '+b'a'*200)
    with pytest.raises(f.Blocked,match='PROJECT_LAUNCHER_ROUTE_CHANGED'):
        f.sources(repo)


def test_historical_pdf_and_zip_not_deleted(sample):
    repo,_,folder=sample
    pdf=folder/'input'/'launch_greeting_card_queue.cmd'
    z=folder/'input'/'accepted.zip'
    hashes=(sha256(pdf.read_bytes()).hexdigest(),sha256(z.read_bytes()).hexdigest())
    f.deploy(folder,f.sources(repo),confirm=True)
    assert hashes==(sha256(pdf.read_bytes()).hexdigest(),sha256(z.read_bytes()).hexdigest())
