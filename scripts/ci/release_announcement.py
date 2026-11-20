"""Annonce WhatsApp d'une release Précis déployée.

Étapes : lire /api/nouveautes de la production, vérifier que `version` est celle du
tag publié (sinon échec, rien n'est envoyé), composer le message, puis l'envoyer
via waha_notify une seule fois par release.

Idempotence : un statut de commit `ANNOUNCE_CONTEXT` sur le SHA de la release.
    success  -> déjà annoncé, re-run = no-op ;
    pending  -> une tentative précédente s'est interrompue pendant l'envoi : échec
                explicite (vérifier le groupe, puis poser success ou failure à la main) ;
    failure / absent -> envoi.
Un pending est posé avant l'envoi, success ou failure après.

Usage :
    python3 release_announcement.py --tag v1.9.0 --dry-run
    python3 release_announcement.py --tag v1.9.0 --sha <release_sha> --repo owner/name
Variables : voir waha_notify ; GITHUB_TOKEN (statuses:write) pour le marqueur.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import waha_notify  # noqa: E402

DEFAULT_ORIGIN = "https://precis-translator.trigenys.com"
ANNOUNCE_CONTEXT = "release/whatsapp-announcement"
DEFAULT_MAX_ITEMS = 8


class AnnounceError(RuntimeError):
    """Échec bloquant de l'annonce (message actionnable, sans secret)."""


# --- Composition (pur, testé) -------------------------------------------------

def version_from_tag(tag: str) -> str:
    tag = tag.strip()
    version = tag[1:] if tag[:1] in ("v", "V") else tag
    parts = version.split(".")
    if len(parts) < 3 or not all(p.isdigit() for p in parts[:2]) or not parts[2].split("-")[0].isdigit():
        raise AnnounceError(f"tag de release non reconnu : {tag!r}")
    return version


def verify_version(payload: dict, expected: str) -> None:
    served = str(payload.get("version", "")).strip()
    if served != expected:
        raise AnnounceError(f"la production sert la version {served or '?'} au lieu de {expected} : "
                            "annonce non envoyée")


def select_elements(payload: dict, since: str | None = None) -> list[dict]:
    """Éléments de cette version : date == date_version, ou since < date <= date_version.

    Ordre : importance (1 d'abord), puis date décroissante, ordre de l'API conservé sinon."""
    date_version = str(payload.get("date_version", ""))
    chosen = []
    for element in payload.get("elements", []):
        date = str(element.get("date", ""))
        if since is not None:
            keep = since < date <= date_version
        else:
            keep = date == date_version
        if keep and element.get("titre"):
            chosen.append(element)
    chosen.sort(key=lambda e: str(e.get("date", "")), reverse=True)
    chosen.sort(key=lambda e: int(e.get("importance") or 3))
    return chosen


def _plain(text: object) -> str:
    """Texte sur une ligne, sans les marqueurs de mise en forme WhatsApp."""
    cleaned = " ".join(str(text or "").split())
    for marker in ("*", "_", "~", "`"):
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip()


def build_message(version: str, elements: list[dict], origin: str = DEFAULT_ORIGIN,
                  max_items: int = DEFAULT_MAX_ITEMS) -> str:
    lines = [f"✅ *Précis Translator {version} est en ligne*", ""]
    shown = elements[:max_items]
    for element in shown:
        title, summary = _plain(element.get("titre")), _plain(element.get("resume"))
        lines.append(f"• *{title}*" + (f" — {summary}" if summary else ""))
    hidden = len(elements) - len(shown)
    if hidden > 0:
        lines.append(f"• … et {hidden} autre{'s' if hidden > 1 else ''} nouveauté{'s' if hidden > 1 else ''}")
    if shown:
        lines.append("")
    lines.append(f"👉 {origin.rstrip('/')}")
    return "\n".join(lines)


# --- Entrées / sorties (injectables) ------------------------------------------

def fetch_json(url: str, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "precis-release-notify"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.load(response)


def fetch_served_release(origin: str, expected: str, *, attempts: int = 5, delay: float = 6.0,
                         fetch: Callable[[str], dict] = fetch_json,
                         sleep: Callable[[float], None] = time.sleep) -> dict:
    """Nouveautés servies, en attendant brièvement que la version déployée apparaisse."""
    url = f"{origin.rstrip('/')}/api/nouveautes"
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            payload = fetch(url)
            verify_version(payload, expected)
            return payload
        except (AnnounceError, urllib.error.URLError, OSError, ValueError) as exc:
            last = exc
            if attempt < attempts:
                sleep(delay)
    if isinstance(last, AnnounceError):
        raise last
    raise AnnounceError(f"{url} illisible : {type(last).__name__}")


class CommitStatusMarker:
    """Marqueur d'annonce porté par un statut de commit GitHub."""

    def __init__(self, repo: str, sha: str, token: str, api: str = "https://api.github.com",
                 request: Callable[..., object] | None = None):
        self.repo, self.sha, self.token, self.api = repo, sha, token, api.rstrip("/")
        self._request = request or self._http

    def _http(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.api}{path}", data=data, method=method, headers={
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "precis-release-notify"})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:  # noqa: S310
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise AnnounceError(f"API GitHub {method} {path} : HTTP {exc.code}") from None

    def state(self) -> str | None:
        statuses = self._request("GET", f"/repos/{self.repo}/commits/{self.sha}/statuses?per_page=100")
        for status in statuses or []:  # plus récent d'abord
            if status.get("context") == ANNOUNCE_CONTEXT:
                return status.get("state")
        return None

    def set(self, state: str, description: str) -> None:
        self._request("POST", f"/repos/{self.repo}/statuses/{self.sha}", {
            "state": state, "context": ANNOUNCE_CONTEXT, "description": description[:140]})


def announce(*, tag: str, origin: str, since: str | None, max_items: int, dry_run: bool,
             marker: CommitStatusMarker | None, env=os.environ,
             fetch: Callable[[str], dict] = fetch_json, sleep=time.sleep,
             send: Callable[..., int] = waha_notify.send_text, out=print) -> str:
    """Renvoie l'issue : dry-run | disabled | already-sent | sent."""
    expected = version_from_tag(tag)
    payload = fetch_served_release(origin, expected, fetch=fetch, sleep=sleep)
    elements = select_elements(payload, since)
    message = build_message(expected, elements, origin, max_items)
    out(f"Version servie : {expected} ({len(elements)} élément(s) de cette version)")
    out("----- message -----\n" + message + "\n-------------------")
    if dry_run:
        out("[dry-run] aucun envoi, aucun marqueur écrit.")
        return "dry-run"
    try:
        config = waha_notify.config_from_env(env)
    except waha_notify.NotifyError as exc:
        raise AnnounceError(str(exc)) from None
    if config is None:
        out("Envoi WhatsApp désactivé (NOTIFY_SESSION / NOTIFY_CHAT_ID absents) : no-op.")
        return "disabled"
    if marker is None:
        raise AnnounceError("marqueur d'idempotence indisponible (--sha, --repo, GITHUB_TOKEN requis)")
    state = marker.state()
    if state == "success":
        out(f"Release {expected} déjà annoncée (statut {ANNOUNCE_CONTEXT}=success) : no-op.")
        return "already-sent"
    if state == "pending":
        raise AnnounceError(
            f"statut {ANNOUNCE_CONTEXT}=pending : une tentative précédente s'est interrompue pendant "
            "l'envoi. Vérifiez le groupe WhatsApp, puis posez le statut success (déjà reçu) ou "
            f"failure (à renvoyer) : gh api repos/{marker.repo}/statuses/{marker.sha} "
            f"-f context={ANNOUNCE_CONTEXT} -f state=failure")
    marker.set("pending", f"Envoi de l'annonce {expected} en cours")
    try:
        send(config, message)
    except waha_notify.NotifyError as exc:
        marker.set("failure", f"Annonce {expected} non envoyée : {exc}")
        raise AnnounceError(str(exc)) from None
    marker.set("success", f"Annonce {expected} envoyée sur WhatsApp")
    out(f"Annonce {expected} envoyée à {config.chat_id}.")
    return "sent"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Annonce WhatsApp d'une release Précis déployée")
    parser.add_argument("--tag", required=True, help="tag publié (ex. v1.9.0)")
    parser.add_argument("--origin", default=os.environ.get("PUBLIC_ORIGIN") or DEFAULT_ORIGIN)
    parser.add_argument("--since", help="date exclusive (AAAA-MM-JJ) : élargit la sélection")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS)
    parser.add_argument("--sha", default=os.environ.get("RELEASE_SHA"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # sortie UTF-8 quel que soit l'OS
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    token = os.environ.get("GITHUB_TOKEN", "")
    marker = CommitStatusMarker(args.repo, args.sha, token) if (args.repo and args.sha and token) else None

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    lines: list[str] = []

    def out(text: str) -> None:
        print(text)
        lines.append(text)

    try:
        outcome = announce(tag=args.tag, origin=args.origin, since=args.since, max_items=args.max_items,
                           dry_run=args.dry_run, marker=marker, out=out)
    except AnnounceError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    finally:
        if summary_path and lines:
            with open(summary_path, "a", encoding="utf-8") as handle:
                handle.write("### Annonce WhatsApp\n\n```text\n" + "\n".join(lines) + "\n```\n")
    print(f"Issue : {outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
