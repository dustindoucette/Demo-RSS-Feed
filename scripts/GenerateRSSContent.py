import hashlib
import os
import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from datetime import datetime
from zoneinfo import ZoneInfo
from feedgen.feed import FeedGenerator

manual_run = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

URL = "https://sta-russell.cdsbeo.on.ca/apps/pages/index.jsp?uREC_ID=1100697&type=d&pREC_ID=1399309"
HASH_FILE = "data/last_hash.txt"

def normalize(text: str) -> str:
    return " ".join(text.split())

def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

os.makedirs("data", exist_ok=True)

# Fetch the page
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

# Extract headings + paragraphs
articles = []
current_title = None
current_paragraphs = []

# We iterate through all tags in main in order
for el in main.descendants:
    # Only consider Tag (not strings directly)
    if isinstance(el, Tag):
        # If it's a header <h2> (or any level), treat as a new item
        if el.name == "h2":
            # Save the previous one
            if current_title and current_paragraphs:
                articles.append({
                    "title": normalize(current_title),
                    "description": normalize(" ".join(current_paragraphs))
                })
            current_title = el.get_text(strip=True)
            current_paragraphs = []
            continue

        # If it's a paragraph, add its text (if we already have a title)
        if el.name == "p" and current_title:
            text = normalize(el.get_text())
            if text:
                current_paragraphs.append(text)

# Capture the last section
if current_title and current_paragraphs:
    articles.append({
        "title": normalize(current_title),
        "description": normalize(" ".join(current_paragraphs))
    })

if not articles:
    raise RuntimeError("No valid announcements found")

# Hash all content
hash_src = "".join(a["title"] + a["description"] for a in articles)
new_hash = hash_content(hash_src)

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

# Build RSS
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
    fe.guid(hash_content(article["title"] + article["description"]), permalink=False)

fg.rss_file("rss.xml")
