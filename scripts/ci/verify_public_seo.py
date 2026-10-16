"""Check the HTTP search-discovery contract against local nginx or production."""
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ORIGIN = sys.argv[1].rstrip("/")
PUBLIC = "https://precis-translator.trigenys.com"
KEY = "baa72b69afa54b709024e6d1d62ae456"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch(path):
    req = urllib.request.Request(ORIGIN + path, headers={"User-Agent": "Googlebot"})
    try:
        response = urllib.request.build_opener(NoRedirect).open(req, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read().decode("utf-8")

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
for path in ["/?share=2", "/home/?share=2", "/index.html?share=2"]:
    status, headers, _ = fetch(path)
    assert status == 308 and headers["Location"] == "/home?share=2", (path, status, headers)
for path in ["/login", "/register", "/verify-email", "/admin/users", "/admin/logs", "/admin/support"]:
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
assert [u.text for u in urls] == [PUBLIC + "/home"]
status, headers, key = fetch("/" + KEY + ".txt")
assert status == 200 and headers.get_content_type() == "text/plain" and key.strip() == KEY
print("PASS: public HTML, canonical redirects, structured data, noindex account/admin pages, real 404s, sitemap, robots and IndexNow key.")
