"""Offline integration: real debs, retained versions, signatures and APT parsing."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync', ROOT / 'scripts/sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

# Only canonical Snout releases enter the pool; other sources retain history.
assert sync.SOURCES['snout'] == 'rustypig91/snout-firmware-explorer'
for tag, expected in [('v0.5.0', None), ('v0.6.0', '0.6.0'),
                      ('0.6.1', '0.6.1'), ('v0.10.0', '0.10.0'),
                      ('v1.0.0', '1.0.0'), ('v0.6.0-alpha.1', None),
                      ('v0.6.0+build', None)]:
    release = {'draft': False, 'prerelease': False, 'tag_name': tag}
    assert sync.supported_release_version('snout', release) == expected
for package in ['pigtail', 'canvaz']:
    release = {'draft': False, 'prerelease': False, 'tag_name': 'v0.5.0'}
    assert sync.supported_release_version(package, release) == '0.5.0'
for flag in ['draft', 'prerelease']:
    release = {'draft': False, 'prerelease': False, 'tag_name': 'v0.6.0'}
    release[flag] = True
    assert sync.supported_release_version('snout', release) is None


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


with tempfile.TemporaryDirectory() as temp:
    work = Path(temp)
    site = work / 'site'
    site.mkdir()
    for package, version in [('pigtail', '1.2.0'), ('pigtail', '1.10.0'),
                             ('canvaz', '1.0.0'), ('snout', '0.6.0-1')]:
        stage = work / f'{package}-{version}'
        (stage / 'DEBIAN').mkdir(parents=True)
        (stage / 'usr/bin').mkdir(parents=True)
        (stage / 'DEBIAN/control').write_text(f'Package: {package}\nVersion: {version}\nArchitecture: amd64\nMaintainer: Test <test@example.invalid>\nDescription: Test fixture\n')
        binary = stage / 'usr/bin' / package
        binary.write_text('#!/bin/sh\nexit 0\n')
        binary.chmod(0o755)
        deb = work / f'{package}-{version}.deb'
        run('dpkg-deb', '--root-owner-group', '--build', str(stage), str(deb))
        sync.ingest(deb, package, site)
        sync.ingest(deb, package, site)  # identical re-import is safe
        binary.write_text('#!/bin/sh\nexit 1\n')
        run('dpkg-deb', '--root-owner-group', '--build', str(stage), str(deb))
        try:
            sync.ingest(deb, package, site)
        except ValueError:
            pass
        else:
            raise AssertionError('Changed published package was accepted')
        if package == 'snout':
            # Old Snout packages lack the canonical executable.
            binary.rename(stage / 'usr/bin/firmware-gui')
            run('dpkg-deb', '--root-owner-group', '--build', str(stage), str(deb))
            try:
                sync.ingest(deb, package, site, '0.6.0')
            except ValueError as error:
                assert 'Missing executable /usr/bin/snout' in str(error)
            else:
                raise AssertionError('Snout without /usr/bin/snout was accepted')
    # This mode covers the metadata producer even where sockets/GPG are blocked.
    if '--packages-only' in sys.argv:
        index = run('dpkg-scanpackages', '--multiversion', 'pool', '/dev/null', cwd=site)
        assert index.count('Package: pigtail\n') == 2
        assert 'Version: 1.10.0' in index
        assert 'Package: snout\nVersion: 0.6.0-1\n' in index
        run('dpkg', '--compare-versions', '1.10.0', 'gt', '1.2.0')
        print('PASS: package validation, immutable imports, retained versions and version ordering')
        sys.exit(0)
    home = work / 'gnupg'
    home.mkdir(mode=0o700)
    env = dict(os.environ, GNUPGHOME=str(home))
    run('gpg', '--batch', '--passphrase', '', '--quick-generate-key',
        'APT fixture <test@example.invalid>', 'rsa2048', 'sign', '1d', env=env)
    fingerprint = next(line.split(':')[9] for line in run('gpg', '--with-colons', '--list-secret-keys', env=env).splitlines() if line.startswith('fpr:'))
    env['APT_GPG_FINGERPRINT'] = fingerprint
    run('bash', str(ROOT / 'scripts/index.sh'), str(site), env=env)
    index = (site / 'dists/stable/main/binary-amd64/Packages').read_text()
    assert index.count('Package: pigtail\n') == 2
    assert 'Version: 1.10.0' in index
    assert 'Package: snout\nVersion: 0.6.0-1\n' in index
    run('dpkg', '--compare-versions', '1.10.0', 'gt', '1.2.0')
    # Isolate APT state completely; no root or system configuration changes.
    state = work / 'apt'
    (state / 'lists/partial').mkdir(parents=True)
    (state / 'cache/archives/partial').mkdir(parents=True)
    (state / 'status').touch()
    sources = state / 'sources.list'
    sources.write_text(f'deb [signed-by={site}/rusty.asc] file:{site} stable main\n')
    options = ['-o', f'Dir::State={state}', '-o', f'Dir::State::status={state}/status',
               '-o', f'Dir::Cache={state}/cache', '-o', f'Dir::Etc::sourcelist={sources}',
               '-o', 'Dir::Etc::sourceparts=-', '-o', 'APT::Get::List-Cleanup=0',
               '-o', 'APT::Sandbox::User=' + os.environ.get('USER', 'root')]
    run('apt-get', *options, 'update')
    simulation = run('apt-get', *options, '--simulate', 'install', 'pigtail', 'canvaz', 'snout')
    assert '1.10.0' in simulation and 'canvaz' in simulation and 'snout' in simulation
print('PASS: package validation, immutability, retained versions, signing, APT update and upgrade selection')
