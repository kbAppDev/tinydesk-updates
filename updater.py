"""GitHub release checks and hash-verified installer downloads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlparse

VERSION = '2.0.0'
REPOSITORY = 'kbAppDev/tinydesk-updates'
RELEASES_URL = f'https://github.com/{REPOSITORY}/releases'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'


def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value)
    if not match:
        raise ValueError('Invalid release version.')
    return tuple(map(int, match.groups()))


def read_url(url, limit=2_000_000):
    request = urllib.request.Request(url, headers={'User-Agent': f'FlareImageCompressor/{VERSION}', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError('Update response is too large.')
        return content


def check():
    release = json.loads(read_url(API_URL))
    if release.get('draft') or release.get('prerelease'):
        raise ValueError('Release is not a stable update.')
    newest = version_tuple(release['tag_name'])
    if newest <= version_tuple(VERSION):
        return None
    name = 'Flare-Image-Compressor-Setup-' + '.'.join(map(str, newest)) + '.exe'
    assets = {asset['name']: asset for asset in release.get('assets', [])}
    if name not in assets or 'SHA256SUMS.txt' not in assets:
        raise ValueError('The new release is missing its installer or checksum.')
    installer = assets[name]['browser_download_url']
    checksum_url = assets['SHA256SUMS.txt']['browser_download_url']
    prefix = f'https://github.com/{REPOSITORY}/releases/download/{release["tag_name"]}/'
    if not installer.startswith(prefix) or not checksum_url.startswith(prefix):
        raise ValueError('Update assets must come from the Flare Tools release repository.')
    checksum = None
    for line in read_url(checksum_url, 30_000).decode('utf-8').splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == name and re.fullmatch('[a-fA-F0-9]{64}', parts[0]):
            checksum = parts[0].lower()
    if not checksum:
        raise ValueError('The installer checksum could not be verified.')
    return {'version': release['tag_name'].lstrip('v'), 'url': installer, 'name': name, 'sha256': checksum}


def download(info, directory: Path, progress=lambda value: None):
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / info['name']
    partial = directory / (info['name'] + '.part')
    digest = hashlib.sha256()
    try:
        request = urllib.request.Request(info['url'], headers={'User-Agent': f'FlareImageCompressor/{VERSION}'})
        with urllib.request.urlopen(request, timeout=30) as response, partial.open('wb') as target:
            length = int(response.headers.get('Content-Length', 0))
            received = 0
            while chunk := response.read(256 * 1024):
                received += len(chunk)
                if received > 150_000_000:
                    raise ValueError('Installer exceeds the download size limit.')
                target.write(chunk)
                digest.update(chunk)
                progress(received / length if length else 0)
        if digest.hexdigest() != info['sha256']:
            raise ValueError('Checksum mismatch. The update was not run; please try again.')
        partial.replace(destination)
        return destination
    finally:
        partial.unlink(missing_ok=True)
