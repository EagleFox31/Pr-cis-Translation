"""Envoi d'un texte WhatsApp via l'API WAHA exposée (POST /api/sendText).

Module générique, sans logique propre à Précis : texte et destinataire en entrée,
clé lue dans l'environnement. Extractible tel quel en action partagée.

Configuration (environnement) :
    NOTIFY_BASE_URL  origine WAHA (défaut https://notify.trigenys.com)
    NOTIFY_SESSION   session WAHA         } absentes toutes deux : envoi désactivé (no-op)
    NOTIFY_CHAT_ID   destinataire (…@g.us) }
    NOTIFY_API_KEY   clé X-Api-Key (secret ; jamais journalisée)

Usage CLI : python3 waha_notify.py --text-file message.txt [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping

DEFAULT_BASE_URL = "https://notify.trigenys.com"


class NotifyError(RuntimeError):
    """Erreur d'envoi ou de configuration, message sans secret."""


@dataclass(frozen=True)
class NotifyConfig:
    base_url: str
    session: str
    chat_id: str
    api_key: str

    def __repr__(self) -> str:  # la clé ne doit jamais apparaître dans un log
        return (f"NotifyConfig(base_url={self.base_url!r}, session={self.session!r}, "
                f"chat_id={self.chat_id!r}, api_key=***)")


def config_from_env(env: Mapping[str, str] = os.environ) -> NotifyConfig | None:
    """Config d'envoi, ou None si l'envoi n'est pas activé (variables absentes).

    Activé à moitié (destinataire sans session, ou sans clé) : erreur explicite,
    pour ne pas taire une configuration incomplète."""
    session = env.get("NOTIFY_SESSION", "").strip()
    chat_id = env.get("NOTIFY_CHAT_ID", "").strip()
    if not session and not chat_id:
        return None
    missing = [name for name, value in (("NOTIFY_SESSION", session), ("NOTIFY_CHAT_ID", chat_id),
                                        ("NOTIFY_API_KEY", env.get("NOTIFY_API_KEY", "").strip()))
               if not value]
    if missing:
        raise NotifyError("configuration WhatsApp incomplète : " + ", ".join(missing) + " manquant(s)")
    base_url = (env.get("NOTIFY_BASE_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/")
    if not base_url.startswith("https://"):
        raise NotifyError("NOTIFY_BASE_URL doit être en https://")
    return NotifyConfig(base_url, session, chat_id, env["NOTIFY_API_KEY"].strip())


Opener = Callable[[urllib.request.Request, float], object]


def _default_opener(request: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310 (https imposé)


def send_text(config: NotifyConfig, text: str, *, timeout: float = 20.0,
              opener: Opener = _default_opener) -> int:
    """POST {session, chatId, text} ; renvoie le code HTTP (2xx) ou lève NotifyError."""
    if not text.strip():
        raise NotifyError("texte vide : rien à envoyer")
    body = json.dumps({"session": config.session, "chatId": config.chat_id, "text": text},
                      ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{config.base_url}/api/sendText", data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "X-Api-Key": config.api_key, "User-Agent": "precis-release-notify"})
    try:
        with opener(request, timeout) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        raise NotifyError(f"envoi WAHA refusé : HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NotifyError(f"envoi WAHA impossible (réseau) : {type(exc).__name__}") from None
    if not 200 <= status < 300:
        raise NotifyError(f"envoi WAHA refusé : HTTP {status}")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--text-file", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # sortie UTF-8 quel que soit l'OS
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    with open(args.text_file, encoding="utf-8") as handle:
        text = handle.read()
    try:
        config = config_from_env()
        if config is None:
            print("Envoi WhatsApp désactivé (NOTIFY_SESSION / NOTIFY_CHAT_ID absents) : no-op.")
            return 0
        if args.dry_run:
            print(f"[dry-run] envoi vers {config.chat_id} (session {config.session}) non effectué.")
            return 0
        send_text(config, text)
    except NotifyError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(f"Message envoyé à {config.chat_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
