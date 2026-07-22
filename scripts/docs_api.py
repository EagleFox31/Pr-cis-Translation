"""Génère la documentation de l'API en une page HTML autonome.

    backend/venv/Scripts/python.exe scripts/docs_api.py

Sortie : `docs/api/index.html` — un seul fichier, sans CDN, sans serveur. On
l'ouvre depuis le disque, on le versionne, on le relit dans une revue de code.

POURQUOI PAS SEULEMENT `/docs`
------------------------------
FastAPI sert déjà Swagger UI. Mais il faut lancer le serveur (donc la base,
LibreOffice, la clé DeepSeek) pour lire une description de route, et rien n'en
reste dans le dépôt : une modification d'API ne se voit pas dans une diff.

C'est le rôle que Scribe joue dans Laravel : la source de vérité reste le code,
et la doc en est un ARTEFACT reproductible. Ici, la source de vérité est le
schéma OpenAPI que FastAPI déduit des signatures et des docstrings — donc une
route mal documentée se voit dans la page, et se corrige dans le code.
"""
from __future__ import annotations

import html
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "backend"))

SORTIE = os.path.join(RACINE, "docs", "api", "index.html")

METHODE_COULEUR = {
    "get": "#2563eb", "post": "#16a34a", "put": "#ca8a04",
    "patch": "#ca8a04", "delete": "#dc2626", "options": "#6b7280",
}


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _md(texte: str) -> str:
    """Rendu minimal : paragraphes, listes, `code`, **gras**.

    Volontairement rudimentaire — la page ne doit dépendre d'aucune
    bibliothèque, et les docstrings du projet n'emploient rien de plus.
    """
    import re
    out, liste = [], False
    for ligne in (texte or "").split("\n"):
        l = ligne.strip()
        if l.startswith(("- ", "• ", "* ")):
            if not liste:
                out.append("<ul>")
                liste = True
            out.append(f"<li>{_e(l[2:])}</li>")
            continue
        if liste:
            out.append("</ul>")
            liste = False
        out.append(f"<p>{_e(l)}</p>" if l else "")
    if liste:
        out.append("</ul>")
    rendu = "\n".join(out)
    rendu = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendu)
    rendu = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendu)
    return rendu


def _exemple_curl(chemin: str, methode: str, op: dict) -> str:
    lignes = [f"curl -X {methode.upper()} \\", "  'http://localhost:8000"
              + chemin + "' \\", "  -H 'X-API-Key: <cle>' \\"]
    if any(p.get("in") == "header" and "auth" in p.get("name", "").lower()
           for p in op.get("parameters", [])) or "/api/" in chemin:
        lignes.append("  -H 'Authorization: Bearer <jeton>' \\")
    corps = op.get("requestBody", {}).get("content", {})
    if "application/json" in corps:
        lignes.append("  -H 'Content-Type: application/json' \\")
        lignes.append("  -d '{}'")
    elif "multipart/form-data" in corps:
        lignes.append("  -F 'file=@document.pdf'")
    else:
        lignes[-1] = lignes[-1].rstrip(" \\")
    return "\n".join(lignes)


def construire() -> str:
    from app import create_app

    spec = create_app().openapi()
    par_tag: dict[str, list] = {}
    for chemin, methodes in sorted(spec.get("paths", {}).items()):
        for methode, op in methodes.items():
            if not isinstance(op, dict):
                continue
            for tag in op.get("tags", ["Autres"]):
                par_tag.setdefault(tag, []).append((chemin, methode, op))

    nav, corps = [], []
    for tag in sorted(par_tag):
        nav.append(f'<div class="grp">{_e(tag)}</div>')
        corps.append(f'<h2 id="tag-{_e(tag)}">{_e(tag)}</h2>')
        for chemin, methode, op in par_tag[tag]:
            ancre = f"{methode}-{chemin}".replace("/", "-").replace("{", "").replace("}", "")
            couleur = METHODE_COULEUR.get(methode, "#6b7280")
            nav.append(
                f'<a href="#{_e(ancre)}"><span class="m" style="color:{couleur}">'
                f'{_e(methode.upper())}</span>{_e(chemin)}</a>')

            resume = op.get("summary") or op.get("operationId", "")
            desc = op.get("description", "")
            params = op.get("parameters", [])

            bloc = [f'<section id="{_e(ancre)}">',
                    f'<h3><span class="badge" style="background:{couleur}">'
                    f'{_e(methode.upper())}</span><code>{_e(chemin)}</code></h3>']
            if resume:
                bloc.append(f'<p class="resume">{_e(resume)}</p>')
            if desc:
                bloc.append(f'<div class="desc">{_md(desc)}</div>')

            if params:
                bloc.append("<h4>Paramètres</h4><table><thead><tr>"
                            "<th>Nom</th><th>Emplacement</th><th>Requis</th>"
                            "<th>Type</th></tr></thead><tbody>")
                for p in params:
                    t = (p.get("schema") or {}).get("type", "—")
                    bloc.append(
                        f'<tr><td><code>{_e(p.get("name"))}</code></td>'
                        f'<td>{_e(p.get("in"))}</td>'
                        f'<td>{"oui" if p.get("required") else "non"}</td>'
                        f'<td>{_e(t)}</td></tr>')
                bloc.append("</tbody></table>")

            bloc.append("<h4>Exemple d'appel</h4>"
                        f"<pre><code>{_e(_exemple_curl(chemin, methode, op))}"
                        "</code></pre>")

            reponses = op.get("responses", {})
            if reponses:
                bloc.append("<h4>Réponses</h4><table><thead><tr><th>Code</th>"
                            "<th>Description</th></tr></thead><tbody>")
                for code, r in sorted(reponses.items()):
                    bloc.append(f'<tr><td><code>{_e(code)}</code></td>'
                                f'<td>{_e(r.get("description", ""))}</td></tr>')
                bloc.append("</tbody></table>")
            bloc.append("</section>")
            corps.append("\n".join(bloc))

    info = spec.get("info", {})
    return _GABARIT.format(
        titre=_e(info.get("title", "API")),
        version=_e(info.get("version", "")),
        description=_md(info.get("description", "")),
        nav="\n".join(nav),
        corps="\n".join(corps),
        n_routes=sum(len(v) for v in par_tag.values()),
    )


_GABARIT = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titre} — documentation</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  color:#1f2937;background:#fff}}
#nav{{position:fixed;top:0;left:0;width:290px;height:100vh;overflow-y:auto;
  border-right:1px solid #e5e7eb;background:#fafafa;padding:20px 0}}
#nav .grp{{padding:14px 18px 6px;font-size:11px;letter-spacing:.08em;
  text-transform:uppercase;color:#6b7280;font-weight:600}}
#nav a{{display:block;padding:5px 18px;text-decoration:none;color:#374151;
  font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
#nav a:hover{{background:#eef2ff}}
#nav .m{{display:inline-block;width:52px;font-weight:700;font-size:10px}}
main{{margin-left:290px;padding:32px 44px;max-width:920px}}
h1{{font-size:28px;margin:0 0 4px}}
h2{{margin:48px 0 8px;padding-bottom:8px;border-bottom:2px solid #e5e7eb;font-size:22px}}
h3{{margin:32px 0 6px;font-size:16px;display:flex;align-items:center;gap:10px}}
h4{{margin:20px 0 6px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;
  color:#6b7280}}
section{{padding:8px 0 20px;border-bottom:1px solid #f3f4f6}}
.badge{{color:#fff;padding:2px 9px;border-radius:4px;font-size:11px;font-weight:700}}
code{{background:#f3f4f6;padding:1px 5px;border-radius:3px;font-size:13px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
pre{{background:#1f2937;color:#e5e7eb;padding:14px 16px;border-radius:6px;
  overflow-x:auto}}
pre code{{background:none;color:inherit;padding:0}}
table{{border-collapse:collapse;width:100%;margin:6px 0 4px}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #e5e7eb;font-size:13px}}
th{{color:#6b7280;font-weight:600;font-size:11px;text-transform:uppercase}}
.resume{{font-weight:600;margin:4px 0}}
.desc p{{margin:6px 0}}
.meta{{color:#6b7280;font-size:13px;margin:0 0 24px}}
.avis{{background:#fffbeb;border-left:3px solid #f59e0b;padding:10px 14px;
  font-size:13px;margin:20px 0}}
@media (max-width:860px){{#nav{{display:none}}main{{margin:0;padding:20px}}}}
@media (prefers-color-scheme:dark){{
  body{{background:#0f172a;color:#e2e8f0}}
  #nav{{background:#111827;border-color:#1f2937}}
  #nav a{{color:#cbd5e1}} #nav a:hover{{background:#1e293b}}
  h2{{border-color:#1f2937}} section{{border-color:#1e293b}}
  code{{background:#1e293b}} th,td{{border-color:#1e293b}}
  .avis{{background:#1e1b0f;border-color:#a16207}}
}}
</style></head><body>
<div id="nav">{nav}</div>
<main>
<h1>{titre}</h1>
<p class="meta">Version {version} · {n_routes} opérations</p>
<div class="desc">{description}</div>
<div class="avis">Page <strong>générée</strong> depuis le schéma OpenAPI de
l'application : <code>python scripts/docs_api.py</code>. Ne pas la modifier à la
main — corriger la docstring ou la signature de la route, puis regénérer.</div>
{corps}
</main></body></html>
"""


def main() -> int:
    page = construire()
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"OK  {os.path.relpath(SORTIE, RACINE)}  ({len(page) // 1024} Ko)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
