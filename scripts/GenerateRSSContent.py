import hashlib
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from feedgen.feed import FeedGenerator

# Detect if this is a manual GitHub Actions run
manual_run = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

URL = "https://sta-russell.cdsbeo.on.ca/apps/pages/DailyAnnouncements"
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

# Target main content
main = soup.find("main")
if not main:
    raise RuntimeError("No main content found on page.")

# Extract <h2> titles and <p> paragraphs beneath them
articles = []
current_title = None
current_paragraphs = []

for el in main.find_all(True, recursive=True):
    if el.name == "h2":
        # Save previous article if exists
        if current_title and current_paragraphs:
            description_html = "".join(f"<p>{normalize(p)}</p>" for p in current_paragraphs)
            articles.append({
                "title": normalize(current_title),
                "description": description_html
            })
        current_title = el.get_text(strip=True)
        current_paragraphs = []
        continue

    # Only grab text from <p> tags
    if el.name == "p" and current_title:
        text = el.get_text(strip=True)
        if text:
            current_paragraphs.append(text)

# Add the last article
if current_title and current_paragraphs:
    description_html = "".join(f"<p>{normalize(p)}</p>" for p in current_paragraphs)
    articles.append({
        "title": normalize(current_title),
        "description": description_html
    })

if not articles:
    raise RuntimeError("No announcements found on the page.")

# Reverse to keep top-of-page first
articles.reverse()

# Compute hash to detect changes
combined_text = "".join(a["title"] + a["description"] for a in articles)
new_hash = hash_content(combined_text)
old_hash = None

if os.path.exists(HASH_FILE):
    old_hash = open(HASH_FILE).read().strip()

# Skip update if unchanged and not manual
if new_hash == old_hash and not manual_run:
    print("No change detected")
    exit(0)

print("Updating RSS feed...")

# Save hash on scheduled runs only
if not manual_run:
    with open(HASH_FILE, "w") as f:
        f.write(new_hash)

# Create RSS feed
fg = FeedGenerator()
fg.title("STA Russell Announcements")
fg.description("Latest announcements from STA Russell")
fg.link(href="https://dustindoucette.github.io/Demo-RSS-Feed", rel="alternate")
fg.link(
    href="https://dustindoucette.github.io/Demo-RSS-Feed/rss.xml",
    rel="self",
    type="application/rss+xml"
)

# Add each article
for article in articles:
    fe = fg.add_entry()
    fe.title(article["title"])
    fe.link(href=URL)
    fe.description(article["description"])  # plain <p> tags, no CDATA
    fe.pubDate(datetime.now(ZoneInfo("America/Toronto")))
    fe.guid(hash_content(article["title"] + article["description"]), permalink=False)

# Write RSS file to repo root
fg.rss_file("rss.xml")
print("RSS feed updated successfully.")
