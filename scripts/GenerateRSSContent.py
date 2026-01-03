import hashlib
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from feedgen.feed import FeedGenerator

# Detect if this is a manual GitHub Actions run
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

# Fetch page
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

# ----------------------------------
# Extract announcements
# ----------------------------------
articles = []

current_title = None
current_body = []

for el in main.find_all(["h2", "h3", "p"]):
    if el.name in ["h2", "h3"]:
        # Save previous article
        if current_title and current_body:
            articles.append({
                "title": normalize(current_title),
                "description": normalize(" ".join(current_body))
            })
        current_title = el.get_text(strip=True)
        current_body = []
    elif el.name == "p" and current_title:
        text = el.get_text(strip=True)
        if text:
            current_body.append(text)

# Capture last article
if current_title and current_body:
    articles.append({
        "title": normalize(current_title),
        "description": normalize(" ".join(current_body))
    })

if not articles:
    raise RuntimeError("No announcements found")

# ----------------------------------
# Hash entire article set
# ----------------------------------
hash_source = "".join(a["title"] + a["description"] for a in articles)
new_hash = hash_content(hash_source)

old_hash = None
if os.path.exists(HASH_FILE):
    old_hash = open(HASH_FILE).read().strip()

# Skip update if unchanged and not a manual run
if new_hash == old_hash and not manual_run:
    print("No change detected")
    exit(0)

print(f"Updating RSS feed with {len(articles)} items")

# Save hash only on scheduled runs
if not manual_run:
    with open(HASH_FILE, "w") as f:
        f.write(new_hash)

# ----------------------------------
# Build RSS
# ----------------------------------
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
    fe.description(article["description"])
    fe.pubDate(now)

    guid_source = article["title"] + article["description"]
    fe.guid(hash_content(guid_source), permalink=False)

# Write RSS file to repo root for GitHub Pages
fg.rss_file("rss.xml")
