#!/usr/bin/env python3
"""Import Précis configuration from a private ZIP into AWS SSM.

Default mode isolates staging. --production preserves application integrations.
Both modes mask values. AWS writes require --apply and the approved account.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import zipfile
import json
from urllib.parse import urlparse

ACCOUNT = "458018461157"
REGION = "eu-west-3"
PARAMETER = "/precis-translation/staging/env"
LIMIT_ZIP = 2 * 1024 * 1024
LIMIT_ENV = 128 * 1024
KEY_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MODEL_NAME = re.compile(r"^[a-zA-Z0-9._-]{3,100}$")


class ImportErrorSafe(ValueError):
    """Messages must never contain environment variable values."""


def parse_env(source: bytes) -> dict[str, str]:
    try:
        contents = source.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportErrorSafe("Un fichier .env n'est pas encodé en UTF-8") from exc
    variables: dict[str, str] = {}
    for number, raw in enumerate(contents.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ImportErrorSafe(f"Ligne .env invalide (ligne {number})")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not KEY_NAME.fullmatch(key) or key in variables:
            raise ImportErrorSafe(f"Nom ou doublon .env non valide (ligne {number})")
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ImportErrorSafe(f"Guillemets .env non fermés (ligne {number})")
            value = value[1:-1]
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ImportErrorSafe(f"Valeur .env non prise en charge (ligne {number})")
        variables[key] = value
    return variables


def read_zip(archive_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    if not archive_path.is_file() or archive_path.stat().st_size > LIMIT_ZIP:
        raise ImportErrorSafe("Archive .zip absente ou trop volumineuse (2 Mio maximum)")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            def pick(suffix: str) -> bytes:
                matches = [entry for entry in archive.infolist()
                           if not entry.is_dir() and
                           (entry.filename == suffix or entry.filename.endswith('/' + suffix)) and
                           '__MACOSX/' not in entry.filename and
                           not entry.filename.startswith('/') and
                           '..' not in entry.filename.split('/')]
                if len(matches) != 1:
                    raise ImportErrorSafe(f"Archive : un seul fichier {suffix} est nécessaire")
                if matches[0].file_size > LIMIT_ENV:
                    raise ImportErrorSafe(f"Archive : {suffix} est trop volumineux")
                with archive.open(matches[0]) as stream:
                    data = stream.read(LIMIT_ENV + 1)
                if len(data) > LIMIT_ENV:
                    raise ImportErrorSafe(f"Archive : {suffix} est trop volumineux")
                return data
            backend = parse_env(pick('backend/.env'))
            frontend = parse_env(pick('frontend/.env'))
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ImportErrorSafe("Archive ZIP non lisible") from exc
    return backend, frontend


def make_staging(backend: dict[str, str], frontend: dict[str, str]) -> dict[str, str]:
    deepseek = backend.get('DEEPSEEK_API_KEY', '').strip()
    if (len(deepseek) < 20 or deepseek.lower() in
            ('your_deepseek_api_key_here', 'changeme', 'replace-me') or
            '\n' in deepseek):
        raise ImportErrorSafe("Clé DEEPSEEK_API_KEY absente ou manifestement factice")
    google_backend = backend.get('GOOGLE_CLIENT_ID', '').strip()
    google_frontend = frontend.get('VITE_GOOGLE_CLIENT_ID', '').strip()
    if google_backend and google_frontend and google_backend != google_frontend:
        raise ImportErrorSafe("Google OAuth : identifiants frontend/backend différents")
    google_id = google_frontend or google_backend
    if google_id and (len(google_id) > 256 or '\n' in google_id or '\r' in google_id):
        raise ImportErrorSafe("Identifiant Google OAuth invalide")
    db_password = secrets.token_urlsafe(36)
    result = {
        'PRECIS_ENV': 'production',  # triggers runtime secret safety checks
        'DEEPSEEK_API_KEY': deepseek,
        'DEEPSEEK_BASE_URL': 'https://api.deepseek.com',
        'FRONTEND_API_KEY': 'precis_fk_' + secrets.token_urlsafe(36),
        'POSTGRES_USER': 'precis',
        'POSTGRES_PASSWORD': db_password,
        'POSTGRES_DB': 'precis',
        'DATABASE_URL': f'postgresql+asyncpg://precis:{db_password}@db:5432/precis',
        'JWT_SECRET': secrets.token_urlsafe(48),
        'EMAIL_ENABLED': 'false',
        'CAMPAY_ENV': 'DEMO',
        'PRICING_DEFAULT_COUNTRY': 'CM',
        'GOOGLE_CLIENT_ID': google_id,
        'ALLOWED_ORIGINS': 'http://localhost',
        'FRONTEND_URL': 'http://localhost',
        'TRANSLATION_WORKERS': '2',
    }
    for key in ('DEEPSEEK_MODEL', 'DEEPSEEK_MODEL_FAST', 'DEEPSEEK_MODEL_PRECISE'):
        supplied = backend.get(key, '').strip()
        if supplied:
            if not MODEL_NAME.fullmatch(supplied):
                raise ImportErrorSafe(f"Nom de modèle {key} invalide")
            result[key] = supplied
    return result


def make_production(backend: dict[str, str], frontend: dict[str, str],
                    public_url: str) -> dict[str, str]:
    """Keep application integrations; generate host-owned secrets on first import."""
    try:
        parsed = urlparse(public_url)
        port = parsed.port
    except ValueError as exc:
        raise ImportErrorSafe("Production : adresse HTTPS invalide") from exc
    if (not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::443)?/?', public_url) or
            parsed.scheme != 'https' or not parsed.hostname or
            parsed.hostname in ('localhost', '127.0.0.1', '::1') or
            parsed.username or parsed.password or port not in (None, 443) or
            parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ImportErrorSafe("Production : --public-url doit être une origine HTTPS publique")
    origin = public_url.rstrip('/')
    result = make_staging(backend, frontend)
    allowed = (
        'DEEPSEEK_MODEL', 'DEEPSEEK_MODEL_FAST', 'DEEPSEEK_MODEL_PRECISE',
        'JWT_EXPIRY_MINUTES', 'REFRESH_TOKEN_EXPIRY_DAYS',
        'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD',
        'CAMPAY_USERNAME', 'CAMPAY_PASSWORD', 'CAMPAY_WEBHOOK_KEY', 'CAMPAY_ENV',
        'PRICING_DEFAULT_COUNTRY', 'TRANSLATION_WORKERS',
        'BRAND_NAME', 'BRAND_TAGLINE', 'ADMIN_ALERT_EMAIL',
        'ERROR_LOG_ALERT_THRESHOLD', 'ERROR_LOG_ALERT_COOLDOWN',
        'ADMIN_EMAIL', 'PAYMENT_METHODS', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_TIMEOUT_S',
        'DEEPSEEK_SOLDE_ALERTE', 'DEEPSEEK_DEPENSE_JOUR_ALERTE',
        'DEEPSEEK_SOLDE_INTERVALLE_S',
    )
    for name in allowed:
        if backend.get(name):
            result[name] = backend[name]
    smtp_ready = bool(result.get('SMTP_USER') and result.get('SMTP_PASSWORD'))
    result['EMAIL_ENABLED'] = backend.get(
        'EMAIL_ENABLED', 'true' if smtp_ready else 'false').lower()
    if result['EMAIL_ENABLED'] not in ('true', 'false'):
        raise ImportErrorSafe("EMAIL_ENABLED doit être true ou false")
    if result['EMAIL_ENABLED'] == 'true' and not smtp_ready:
        raise ImportErrorSafe("E-mails activés : SMTP_USER et SMTP_PASSWORD requis")
    if result['CAMPAY_ENV'] not in ('DEMO', 'PROD'):
        raise ImportErrorSafe("CAMPAY_ENV doit être DEMO ou PROD")
    if result['CAMPAY_ENV'] == 'PROD' and not all(
            result.get(k) for k in ('CAMPAY_USERNAME', 'CAMPAY_PASSWORD', 'CAMPAY_WEBHOOK_KEY')):
        raise ImportErrorSafe("Campay PROD : identifiants et clé de webhook requis")
    result['FRONTEND_URL'] = origin
    result['ALLOWED_ORIGINS'] = origin
    result['PUBLIC_SITE'] = parsed.hostname
    return result


def preserve_existing_secrets(payload: dict[str, str]) -> bool:
    """Never rotate the database password or signing key during a re-import."""
    process = subprocess.run(
        ['aws', '--no-cli-pager', 'ssm', 'get-parameter', '--region', REGION,
         '--name', PARAMETER, '--with-decryption', '--output', 'json'],
        capture_output=True, text=True, check=False)
    if process.returncode:
        if 'ParameterNotFound' in process.stderr:
            return False
        raise ImportErrorSafe("Lecture SSM refusée : impossible de préserver les secrets existants")
    try:
        existing = parse_env(json.loads(process.stdout)['Parameter']['Value'].encode('utf-8'))
    except (KeyError, ValueError, TypeError) as exc:
        raise ImportErrorSafe("Configuration SSM existante non lisible") from exc
    for key in ('POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB', 'JWT_SECRET', 'FRONTEND_API_KEY'):
        if not existing.get(key):
            raise ImportErrorSafe(f"Configuration SSM existante incomplète : {key}")
        payload[key] = existing[key]
    payload.pop('DATABASE_URL', None)  # Compose derives it from preserved POSTGRES_*.
    return True


def aws(args: list[str]) -> str:
    process = subprocess.run(['aws', '--no-cli-pager', *args],
                             capture_output=True, text=True, check=False)
    if process.returncode:
        # AWS CLI may echo details; never echo stderr or the command arguments.
        raise ImportErrorSafe("L'appel AWS a été refusé. Vérifie tes permissions et le compte AWS")
    return process.stdout.strip()


def put_ssm(payload: dict[str, str], production: bool = False) -> None:
    caller = aws(['sts', 'get-caller-identity', '--query', 'Account', '--output', 'text'])
    if caller != ACCOUNT:
        raise ImportErrorSafe("Mauvais compte AWS : import refusé")
    overwrite = preserve_existing_secrets(payload) if production else False
    value = '\n'.join(f'{name}={value}' for name, value in payload.items()) + '\n'
    if len(value.encode('utf-8')) > 4096:
        raise ImportErrorSafe("Configuration trop grande pour SSM Standard (4096 octets)")
    staging_file: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         prefix='precis-ssm-', delete=False) as handle:
            staging_file = handle.name
            os.fchmod(handle.fileno(), 0o600)
            handle.write(value)
        aws(['ssm', 'put-parameter', '--region', REGION, '--name', PARAMETER,
             '--type', 'SecureString', '--tier', 'Standard',
             '--value', 'file://' + staging_file] + (['--overwrite'] if overwrite else []))
    finally:
        if staging_file:
            Path(staging_file).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description='Précis : import ZIP .env vers AWS SSM chiffré')
    parser.add_argument('archive', type=Path, help='precis-env.zip avec backend/.env et frontend/.env')
    parser.add_argument('--apply', action='store_true', help='Créer le paramètre SSM SecureString')
    parser.add_argument('--production', action='store_true',
                        help='Conserver les intégrations de production du ZIP')
    parser.add_argument('--public-url', default='', help='Origine HTTPS de production')
    args = parser.parse_args()
    try:
        backend, frontend = read_zip(args.archive)
        if args.production and not args.public_url:
            raise ImportErrorSafe("Production : --public-url est obligatoire")
        payload = (make_production(backend, frontend, args.public_url)
                   if args.production else make_staging(backend, frontend))
        print('Variables retenues (valeurs masquées) :')
        for name in payload:
            print(f'  {name}=********')
        if args.production:
            print('Mode production : intégrations SMTP, Google et Campay conservées selon le ZIP.')
            print('Secrets PostgreSQL/JWT/frontend existants préservés lors de réimportation.')
            print('Le chemin SSM historique staging/env reste utilisé par les rôles IAM installés.')
            print('Cet import ne crée pas de serveur et ne configure pas les DNS.')
        else:
            print('Ignorés : mots de passe Campay, SMTP, Google OAuth secret, JWT et PostgreSQL existants.')
        if not args.production:
            print('Secrets de staging JWT, PostgreSQL et frontend : nouvelles valeurs générées.')
        if not args.apply:
            print('Prévisualisation seulement. Relancer avec --apply pour importer dans SSM.')
            return 0
        put_ssm(payload, production=args.production)
        args.archive.unlink(missing_ok=True)  # do not keep uploaded production secrets in CloudShell
        print(f'Import SSM SecureString réussi : {PARAMETER} ({REGION}).')
        print('Archive téléchargée dans CloudShell supprimée après succès.')
        return 0
    except ImportErrorSafe as error:
        print(f'Import refusé : {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
