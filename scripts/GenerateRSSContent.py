import hashlib
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from feedgen.feed import FeedGenerator
from xml.dom import minidom

# Detect manual GitHub Actions run
manual_run = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

URL = "https://sta-russell.cdsbeo.on.ca/apps/pages/index.jsp?uREC_ID=1100697&type=d&pREC_ID=1399309"
HASH_FILE = "data/last_hash.txt"

def normalize(text: str) -> str:
    """Normalize whitespace in text."""
    return " ".join(text.split())

def hash_content(text: str) -> str:
    """Return SHA256 hash of the given text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

# ---------------------------
# Fetch page
# ---------------------------
res = requests.get(
    URL,
    headers={"User-Agent": "RSS-Monitor/1.0"},
    timeout=15
)
res.raise_for_status()

soup = BeautifulSoup(res.text, "html.parser")
main = soup.find("main")
if not main:
    raise RuntimeError("Main content not found")

# ---------------------------
# Extract headers (<h2>) + paragraphs in page order
# ---------------------------
articles = []
current_title = None
current_paragraphs = []

for el in main.find_all(True, recursive=True):
    if el.name == "h2":
        if current_title and current_paragraphs:
            description_html = "".join(f"<p>{p}</p>" for p in current_paragraphs)
            articles.append({
                "title": normalize(current_title),
                "description": description_html
            })
        current_title = el.get_text(strip=True)
        current_paragraphs = []
        continue

    if el.name == "p" and current_title:
        text = normalize(el.get_text())
        if text:
            current_paragraphs.append(text)

# Add the last section
if current_title and current_paragraphs:
    description_html = "".join(f"<p>{p}</p>" for p in current_paragraphs)
    articles.append({
        "title": normalize(current_title),
        "description": description_html
    })

if not articles:
    raise RuntimeError("No announcements found")

# ---------------------------
# Hash content
# ---------------------------
hash_source = "".join(a["title"] + a["description"] for a in articles)
new_hash = hash_content(hash_source)

old_hash = None
if os.path.exists(HASH_FILE):
    old_hash = open(HASH_FILE).read().strip()

if new_hash == old_hash and not manual_run:
    print("No change detected")
    exit(0)

print(f"Updating RSS feed with {len(articles)} items")

if not manual_run:
    with open(HASH_FILE, "w") as f:
        f.write(new_hash)

# ---------------------------
# Build RSS feed
# ---------------------------
fg = FeedGenerator()
fg.title("STA Russell Announcements")
fg.description("Latest announcements from STA Russell")
fg.link(href=URL, rel="alternate")
fg.link(
    href="https://dustindoucette.github.io/Demo-RSS-Feed/rss.xml",
    rel="self",
    type="application/rss+xml"
)

now = datetime.now(ZoneInfo("America/Toronto"))

for article in articles:
    fe = fg.add_entry()
    fe.title(article["title"])
    fe.link(href=URL)
    fe.description(article["description"])  # HTML <p> tags included
    fe.pubDate(now)
    fe.guid(hash_content(article["title"] + article["description"]), permalink=False)

# ---------------------------
# Pretty-print XML and save
# ---------------------------
rss_bytes = fg.rss_str(pretty=True)
dom = minidom.parseString(rss_bytes)
pretty_xml = dom.toprettyxml(indent="  ", encoding="UTF-8")

with open("rss.xml", "wb") as f:
    f.write(pretty_xml)

print("RSS feed saved to rss.xml")
