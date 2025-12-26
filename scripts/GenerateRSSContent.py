import hashlib
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from feedgen.feed import FeedGenerator

# Detect if this is a manual GitHub Actions run
manual_run = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

URL = "https://sta-russell.cdsbeo.on.ca/apps/news/"
HASH_FILE = "data/last_hash.txt"

def normalize(text: str) -> str:
    """Normalize whitespace in text."""
    return " ".join(text.split())

def hash_content(text: str) -> str:
    """Return SHA256 hash of the given text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

# Fetch content
res = requests.get(
    URL,
    headers={"User-Agent": "RSS-Monitor/1.0"},
    timeout=15
)
res.raise_for_status()

soup = BeautifulSoup(res.text, "html.parser")

# Target stable main content
main = soup.find("main")
content = normalize(main.get_text()) if main else normalize(soup.get_text())

# Compute content hash
new_hash = hash_content(content)
old_hash = None

if os.path.exists(HASH_FILE):
    old_hash = open(HASH_FILE).read().strip()

# Skip update if unchanged and not a manual run
if new_hash == old_hash and not manual_run:
    print("No change detected")
    exit(0)

print("Updating RSS feed...")

# Save hash only on scheduled runs
if not manual_run:
    with open(HASH_FILE, "w") as f:
        f.write(new_hash)

# Create RSS feed
fg = FeedGenerator()
fg.title("Change Monitor Feed")
fg.description("Updates only when content changes")

# Main site link
fg.link(href="https://dustindoucette.github.io/Demo-RSS-Feed", rel="alternate")

# Atom self-link for feed readers
fg.link(
    href="https://dustindoucette.github.io/Demo-RSS-Feed/rss.xml",
    rel="self",
    type="application/rss+xml"
)

# Add feed entry
fe = fg.add_entry()
fe.title("Content Updated")
fe.link(href=URL)
fe.content(content[:1000] + "…", type="CDATA")  # correct CDATA usage
fe.pubDate(datetime.now(ZoneInfo("America/Toronto")))
fe.guid(new_hash, permalink=False)

# Write RSS file to repo root for GitHub Pages
fg.rss_file("rss.xml")
