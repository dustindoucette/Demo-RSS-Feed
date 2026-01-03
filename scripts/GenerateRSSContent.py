import hashlib
import os
import requests
from bs4 import BeautifulSoup
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
# Extract announcements (robust)
# ----------------------------------
articles = []

for block in main.find_all("div"):
    strong = block.find("strong")
    if not strong:
        continue

    title = normalize(strong.get_text())
    full_text = normalize(block.get_text())

    # Remove title from description
    description = full_text.replace(title, "").strip()

    if title and description and len(description) > 40:
        articles.append({
            "title": title,
            "description": description
        })

if not articles:
    raise RuntimeError("No announcements found (structure may have changed)")

# ----------------------------------
# Hash content
# ----------------------------------
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
    fe.guid(hash_content(article["title"] + article["description"]), permalink=False)

fg.rss_file("rss.xml")
