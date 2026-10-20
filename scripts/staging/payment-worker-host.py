"""Stage one worker image with isolated sandbox/live configuration; no PSP calls."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = Path('/opt/trigenys/payment-orchestrator-sandbox')
SOURCE_SHA = 'a27c930ed5de36f09d8e74d2748adb66824576b5'


def command(args, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Host operation failed: ' + args[0])
    return result.stdout


def application_state():
    names = command(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()
    names = sorted(name for name in names if name.startswith('precis-translation-staging-'))
    if not names:
        raise RuntimeError('Existing Precis containers were not found')
    result = {}
    for name in names:
        record = json.loads(command(['docker', 'inspect', name]))[0]
        result[name] = {
            'id': record['Id'], 'startedAt': record['State']['StartedAt'],
            'status': record['State']['Status'],
            'health': record['State'].get('Health', {}).get('Status')
        }
    if any(row['status'] != 'running' or row['health'] == 'unhealthy' for row in result.values()):
        raise RuntimeError('Existing Precis service is not healthy; staging refused')
    return result


def capacity():
    fields = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    memory_mb = int(fields['MemAvailable'].split()[0]) // 1024
    disk_mb = shutil.disk_usage('/opt').free // (1024 * 1024)
    cpus = os.cpu_count() or 1
    result = {'available_memory_mb': memory_mb, 'free_disk_mb': disk_mb, 'cpus': cpus}
    result['sufficient'] = memory_mb >= 256 and disk_mb >= 2048
    return result


def download_image(url, digest, directory):
    parsed = urllib.parse.urlparse(url)
    allowed = ('.blob.core.windows.net', '.actions.githubusercontent.com', '.githubusercontent.com')
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith(allowed):
        raise RuntimeError('Artifact download origin refused')
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise RuntimeError('Artifact digest is invalid')
    archive = directory / 'artifact.zip'
    # Only public source/dependencies are transported; this short-lived signed URL
    # is never printed. There are no runtime credentials in the image/artifact.
    with urllib.request.urlopen(url, timeout=30) as response, archive.open('wb') as output:
        count = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            count += len(chunk)
            if count > 768 * 1024 * 1024:
                raise RuntimeError('Artifact is too large')
            output.write(chunk)
    image = directory / 'payment-worker.tar.gz'
    with zipfile.ZipFile(archive) as bundle:
        item = bundle.getinfo('payment-worker.tar.gz')
        if item.file_size > 768 * 1024 * 1024:
            raise RuntimeError('Image archive is too large')
        with bundle.open(item) as source, image.open('wb') as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
    checksum = hashlib.sha256()
    with image.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(chunk)
    if checksum.hexdigest() != digest:
        raise RuntimeError('Image checksum mismatch')
    return image


def stage(config):
    if os.geteuid() != 0:
        raise RuntimeError('Host staging requires root for Docker and protected files')
    before = application_state()
    available = capacity()
    print(json.dumps({'capacity': available}), flush=True)
    if not available['sufficient']:
        raise RuntimeError('Insufficient spare capacity; no worker installed')
    image_id = config['image_id']
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id) or config['source_sha'] != SOURCE_SHA:
        raise RuntimeError('Image identity refused')
    if ROOT.is_symlink():
        raise RuntimeError('Worker directory must not be a symlink')
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    ROOT.chmod(0o700)
    with tempfile.TemporaryDirectory(prefix='worker-stage-', dir=ROOT) as temporary:
        image = download_image(config['archive_url'], config['archive_sha256'], Path(temporary))
        command(['docker', 'load', '--input', str(image)], timeout=240)
    metadata = json.loads(command(['docker', 'inspect', '--type=image', image_id]))[0]
    if metadata['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != SOURCE_SHA:
        raise RuntimeError('Loaded worker source revision mismatch')
    # Import-only smoke test: network disabled, no secrets, no PSP/database call.
    smoke = command([
        'docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--memory=128m', '--memory-swap=128m',
        '--cpus=0.25', '--pids-limit=64', '--user=node', image_id,
        'node', '--input-type=module', '-e',
        'await import("./dist/src/worker/run-once.js"); console.log("payment worker import OK")'
    ], timeout=60)
    if 'payment worker import OK' not in smoke:
        raise RuntimeError('Worker import verification failed')
    installed = []
    for environment in ('sandbox', 'live'):
        directory = ROOT if environment == 'sandbox' else ROOT.with_name('payment-orchestrator-live')
        if directory.is_symlink():
            raise RuntimeError('Worker environment directory must not be a symlink')
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        env_file = directory / 'runtime.env'
        if env_file.is_symlink():
            raise RuntimeError('Worker environment must not be a symlink')
        if not env_file.exists():
            suffix = environment.upper()
            template = (f'PAYMENT_ENVIRONMENT={environment}\nPAYMENT_SWEEP_ENABLED=false\n'
                        f'PAYMENT_{suffix}_DATABASE_URL=\n'
                        f'PAYMENT_{suffix}_PROJECT_ID=\nPAYMENT_{suffix}_MERCHANT_ID=\n'
                        f'FAPSHI_{suffix}_SERVICE_NAME=\nFAPSHI_{suffix}_APIUSER=\nFAPSHI_{suffix}_APIKEY=\n')
            fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as target:
                target.write(template)
        env_file.chmod(0o600)
        script = directory / f'run-{environment}-once'
        script_args = ['/usr/bin/docker', 'run', '--rm', '--read-only', '--cap-drop=ALL',
                       '--security-opt=no-new-privileges', '--memory=128m', '--memory-swap=128m',
                       '--cpus=0.25', '--pids-limit=64', '--user=node', '--env-file',
                       str(env_file), '--env', f'PAYMENT_ENVIRONMENT={environment}',
                       image_id, 'node', 'dist/src/worker/run-once.js']
        script_text = '#!/bin/sh\nset -eu\nexec ' + shlex.join(script_args) + '\n'
        temporary_script = script.with_suffix('.new')
        temporary_script.write_text(script_text)
        temporary_script.chmod(0o700)
        temporary_script.replace(script)
        installed.append({'environment': environment, 'directory': str(directory)})
    # Never install a timer, open a port, restart Precis, or modify its env.
    if application_state() != before:
        raise RuntimeError('Precis container state changed during staging; inspect before proceeding')
    record = {'source_sha': SOURCE_SHA, 'image_id': image_id, 'installed_at': int(time.time()),
              'smoke_test': 'passed', 'regular_processing_enabled': False,
              'precis_containers_unchanged': True, 'capacity': available, 'environments': installed}
    for item in installed:
        record_file = Path(item['directory']) / 'deployment.json'
        record_file.write_text(json.dumps({**record, 'environment': item['environment']}, indent=2) + '\n')
        record_file.chmod(0o600)
    print(json.dumps(record), flush=True)


def main(config):
    if config['mode'] == 'inspect':
        print(json.dumps({'capacity': capacity(), 'precis': application_state()}), flush=True)
    elif config['mode'] == 'stage':
        stage(config)
    else:
        raise RuntimeError('Unknown payment worker operation')
