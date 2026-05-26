import asyncio
import json
import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from browser_use_sdk import AsyncBrowserUse

from sites import SITES

load_dotenv()

OUTPUT_DIR = Path("data/articles")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CUTOFF_DATE = date(2024, 3, 26)  # 2 years back from today


class Article(BaseModel):
    title: str
    url: str
    date: str
    summary: str


class ArticleBatch(BaseModel):
    articles: list[Article]
    has_more_pages: bool
    next_page_url: str | None = None


def build_prompt(site: dict, page_url: str | None = None) -> str:
    url = page_url or site["url"]
    return (
        f"Go to {url}. "
        f"For each headline on this page published after 2025, extract the title and the date it was published (YYYY-MM-DD). "
        f"If the date is not visible or retrievable through metadata, open the article and check."
        f"If there is a 'load more' or 'next page' button, click it to access more articles." 
        f"Alternatively, if the page is an archive, there may be a series of months and days before the headlines can be accessed."
        f"Add each retrieved title and date to a csv with the columns 'title' and 'date' and return the csv."
    )


async def scrape_site(client: AsyncBrowserUse, site: dict) -> list[Article]:
    all_articles = []
    page_url = None
    page_num = 0

    while True:
        page_num += 1
        prompt = build_prompt(site, page_url)
        print(f"  [{site['name']}] page {page_num}: scraping...")

        result = await client.run(
            prompt,
            output_schema=ArticleBatch,
            llm="browser-use-2.0",
        )

        batch: ArticleBatch = result.output
        new_count = len(batch.articles)
        all_articles.extend(batch.articles)
        print(f"  [{site['name']}] page {page_num}: got {new_count} articles")

        if not batch.has_more_pages or not batch.next_page_url:
            break

        page_url = batch.next_page_url

    return all_articles


def save_articles(site_name: str, articles: list[Article]):
    out_path = OUTPUT_DIR / f"{site_name}.json"
    data = [a.model_dump() for a in articles]
    out_path.write_text(json.dumps(data, indent=2))
    print(f"  [{site_name}] saved {len(data)} articles to {out_path}")


async def main():
    if not SITES:
        print("No sites configured. Edit sites.py to add your news sites.")
        return

    client = AsyncBrowserUse()

    for site in SITES:
        name = site["name"]
        print(f"\n--- {name} ---")
        try:
            articles = await scrape_site(client, site)
            save_articles(name, articles)
        except Exception as e:
            print(f"  [{name}] FAILED: {e}")

    await client.close()

    total = sum(
        len(json.loads(f.read_text()))
        for f in OUTPUT_DIR.glob("*.json")
    )
    print(f"\nDone. {total} total articles across {len(SITES)} sites.")


if __name__ == "__main__":
    asyncio.run(main())
