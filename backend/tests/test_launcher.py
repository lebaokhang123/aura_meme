"""Windows entrypoint regression: default demo and no broken empty-schema UI."""
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


BAT = Path(__file__).resolve().parents[2] / 'run.bat'


@pytest.mark.skipif(os.name != 'nt', reason='Windows CMD launcher')
@pytest.mark.parametrize(('args', 'mode'), [([], 'demo'), (['demo'], 'demo'), (['DEMO'], 'demo'), (['dev'], 'dev')])
def test_launcher_mode_selection(tmp_path, args, mode):
    # Execute the real argument parser without starting services or opening a browser.
    header = BAT.read_text(encoding='utf-8').split('set "AURAMEME_LAUNCHER=', 1)[0]
    fixture = tmp_path / 'mode.bat'
    fixture.write_text(header + 'echo MODE=%AURAMEME_MODE%\nexit /b 0\n', encoding='utf-8')
    result = subprocess.run([os.environ['COMSPEC'], '/d', '/c', str(fixture), *args],
                            input='\n', capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout
    assert 'MODE=' + mode in result.stdout


@pytest.mark.skipif(os.name != 'nt', reason='Windows CMD launcher')
@pytest.mark.parametrize('args', [['unknown'], ['demo', 'extra']])
def test_launcher_rejects_invalid_arguments(tmp_path, args):
    header = BAT.read_text(encoding='utf-8').split('set "AURAMEME_LAUNCHER=', 1)[0]
    fixture = tmp_path / 'mode.bat'
    fixture.write_text(header + 'echo ACCEPTED\n', encoding='utf-8')
    result = subprocess.run([os.environ['COMSPEC'], '/d', '/c', str(fixture), *args],
                            input='\n', capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'ACCEPTED' not in result.stdout


def test_empty_database_stops_before_servers(monkeypatch, capsys):
    ns = {'__file__': str(BAT), '__name__': 'launcher_test'}
    exec(compile(BAT.read_text(encoding='utf-8').split('\n# AURAMEME_PYTHON\n', 1)[1], str(BAT), 'exec'), ns)
    for key, value in {'DEMO': False, 'windows': lambda: object(),
                       'claim_launcher': lambda api: (0, 0), 'prerequisites': lambda: 'node',
                       'listeners': lambda: {8000: set(), 5173: set()}}.items():
        monkeypatch.setitem(ns, key, value)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout='{"schema":"empty"}'))
    spawned = []

    def reject_spawn(*args, **kwargs):
        spawned.append(args)
        raise AssertionError('Server must not start without a schema')

    monkeypatch.setattr(subprocess, 'Popen', reject_spawn)
    assert ns['main']() == 1
    assert spawned == []
    assert 'run.bat demo' in capsys.readouterr().out
