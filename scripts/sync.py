#!/usr/bin/env python3
"""Reconcile all public stable releases into an immutable package pool."""
import hashlib
import json
import pathlib
import re
import subprocess
import tarfile
import tempfile
import urllib.request

SOURCES = {'pigtail': 'rustypig91/pigtail-serial-console', 'canvaz': 'rustypig91/canvaz'}


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def ingest(asset, package, root, release_version=None):
    run('dpkg-deb', '--info', str(asset))
    run('dpkg-deb', '--contents', str(asset))
    name, version, arch = [run('dpkg-deb', '-f', str(asset), field)
                           for field in ('Package', 'Version', 'Architecture')]
    if name != package or arch not in ('amd64', 'arm64', 'armhf', 'i386', 'all'):
        raise ValueError(f'Unexpected package identity: {name} {arch}')
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+~:-]*', version):
        raise ValueError('Unsafe version')
    run('dpkg', '--validate-version', version)
    if release_version and not (version == release_version or version.startswith(release_version + '-')):
        raise ValueError(f'Package version {version} does not match release {release_version}')
    proc = subprocess.Popen(['dpkg-deb', '--fsys-tarfile', str(asset)], stdout=subprocess.PIPE)
    executable = False
    with tarfile.open(fileobj=proc.stdout, mode='r|') as tar:
        for member in tar:
            if member.name.lstrip('./') == f'usr/bin/{package}':
                executable = member.isfile() and bool(member.mode & 0o111)
    if proc.wait() or not executable:
        raise ValueError(f'Missing executable /usr/bin/{package}')
    destination = root / 'pool/main' / package[0] / package / f'{name}_{version}_{arch}.deb'
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = asset.read_bytes()
    if destination.exists() and hashlib.sha256(destination.read_bytes()).digest() != hashlib.sha256(data).digest():
        raise ValueError(f'Refusing to overwrite immutable package {destination}')
    destination.write_bytes(data)


def main():
    for package, repository in SOURCES.items():
        pages = json.loads(run('gh', 'api', '--paginate', '--slurp', f'repos/{repository}/releases?per_page=100'))
        for page in pages:
            for release in page:
                if release['draft'] or release['prerelease']:
                    continue
                if not re.fullmatch(r'v?\d+\.\d+\.\d+', release['tag_name']):
                    continue
                for asset in release['assets']:
                    # Legacy Canvaz assets retain their display-title identity.
                    if not asset['name'].startswith(package + '_') or not asset['name'].endswith('.deb'):
                        continue
                    with tempfile.TemporaryDirectory() as temp:
                        path = pathlib.Path(temp) / 'package.deb'
                        urllib.request.urlretrieve(asset['browser_download_url'], path)
                        ingest(path, package, pathlib.Path('site'), release['tag_name'].removeprefix('v'))


if __name__ == '__main__':
    main()
