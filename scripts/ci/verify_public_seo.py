"""Check the HTTP search-discovery contract against local nginx or production."""
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ORIGIN = sys.argv[1].rstrip("/")
PUBLIC = "https://precis-translator.trigenys.com"
KEY = "baa72b69afa54b709024e6d1d62ae456"
REPO = Path(__file__).resolve().parents[2]
SITE = json.loads((REPO / "frontend/seo/site.json").read_text(encoding="utf-8"))
ROUTES = [route["path"] for route in SITE["routes"]]
DEPLOY_URL = json.loads((REPO / "deploy/public-site.json").read_text(encoding="utf-8"))["url"]
assert SITE["origin"] == PUBLIC == DEPLOY_URL, (SITE["origin"], PUBLIC, DEPLOY_URL)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch(path, **extra):
    req = urllib.request.Request(ORIGIN + path, headers={"User-Agent": "Googlebot", **extra})
    try:
        response = urllib.request.build_opener(NoRedirect).open(req, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read()
        if response.headers.get("Content-Encoding"):
            return response.status, response.headers, body
        return response.status, response.headers, body.decode("utf-8")

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonicals = []
        self.headings = 0
        self.jsonld = []
        self.in_jsonld = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonicals.append(attrs.get("href"))
        if tag == "h1":
            self.headings += 1
        if tag == "script":
            self.in_jsonld = attrs.get("type") == "application/ld+json"
    def handle_endtag(self, tag):
        if tag == "script":
            self.in_jsonld = False
    def handle_data(self, data):
        if self.in_jsonld:
            self.jsonld.append(json.loads(data))

status, headers, html = fetch("/home")
assert status == 200 and "noindex" not in headers.get("X-Robots-Tag", "")
page = Page()
page.feed(html)
assert page.canonicals == [PUBLIC + "/home"]
assert page.headings == 1 and "Précis Translator" in html and "DOCX" in html
assert any(node["@type"] == "SoftwareApplication" for node in page.jsonld[0]["@graph"])
assert all(f'href="{path}"' in html for path in ROUTES), "home must link every public page"
for path in ROUTES[1:]:
    status, headers, html = fetch(path)
    assert status == 200 and "noindex" not in headers.get("X-Robots-Tag", ""), (path, status)
    page = Page()
    page.feed(html)
    assert page.canonicals == [PUBLIC + path] and page.headings == 1, (path, page.canonicals, page.headings)
    graph = page.jsonld[0]["@graph"]
    assert any(n["@type"] == "WebPage" and n["url"] == PUBLIC + path for n in graph), path
    assert all(f'href="{other}"' in html for other in ROUTES), path
status, _, html = fetch("/extension")
extension = Page()
extension.feed(html)
faq = [n for n in extension.jsonld[0]["@graph"] if n["@type"] == "FAQPage"]
assert faq and all(q["name"] in html and q["acceptedAnswer"]["text"] in html for q in faq[0]["mainEntity"])
status, headers, _ = fetch("/home", **{"Accept-Encoding": "gzip", "Via": "1.1 Caddy"})
assert status == 200 and headers.get("Content-Encoding") == "gzip", "proxied HTML must be compressed"
for path in ["/?share=2", "/home/?share=2", "/index.html?share=2", "/index?share=2"]:
    status, headers, _ = fetch(path)
    assert status == 308 and headers["Location"] == "/home?share=2", (path, status, headers)
for path in ["/login", "/register", "/verify-email", "/beta", "/beta/", "/admin/users", "/admin/logs", "/admin/support", "/admin/beta"]:
    status, headers, _ = fetch(path)
    assert status == 200 and "noindex" in headers.get("X-Robots-Tag", ""), path
for path in ["/missing-seo-page", "/missing-seo-file.txt", "/assets/missing-seo.js"]:
    assert fetch(path)[0] == 404, path
status, _, robots = fetch("/robots.txt")
assert status == 200 and "Sitemap: " + PUBLIC + "/sitemap.xml" in robots
assert "Disallow: /\n" not in robots and "Disallow: /login" not in robots
status, headers, xml = fetch("/sitemap.xml")
assert status == 200 and "xml" in headers.get_content_type()
urls = ET.fromstring(xml).findall("{*}url/{*}loc")
assert [u.text for u in urls] == [PUBLIC + path for path in ROUTES]
status, headers, llms = fetch("/llms.txt")
assert status == 200 and headers.get_content_type() == "text/plain" and llms.startswith("# ")
assert all(PUBLIC + path in llms for path in ROUTES), "llms.txt must list every public page"
status, headers, key = fetch("/" + KEY + ".txt")
assert status == 200 and headers.get_content_type() == "text/plain" and key.strip() == KEY
print("PASS: prerendered public pages, canonical redirects, structured data, compression, noindex account/admin pages, real 404s, sitemap, llms.txt, robots and IndexNow key.")
