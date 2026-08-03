"""
Crossref Fetcher
Retrieves recent journal articles from Crossref's REST API by ISSN.
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r'<[^>]+>')


def _clean_text(text: Optional[str]) -> str:
    """Strip JATS/HTML-style tags and collapse whitespace."""
    if not text:
        return ''
    stripped = _TAG_RE.sub('', text)
    return re.sub(r'\s+', ' ', stripped).strip()


class CrossrefFetcher:
    """Fetches recent journal articles from Crossref by ISSN."""

    BASE_URL = "https://api.crossref.org/journals"

    def __init__(self, sources: Dict[str, str], mailto: str):
        """
        Initialize Crossref fetcher.

        Args:
            sources: Dictionary mapping display name to ISSN
            mailto: Contact email for Crossref's polite pool
        """
        self.sources = sources
        self.mailto = mailto

    def fetch_recent_articles(self, days: int = 8) -> List[Dict]:
        """
        Fetch articles from all configured journals from the past N days.

        Args:
            days: Number of days to look back (default 8)

        Returns:
            List of article dictionaries, same shape as returned by the previous
            RSS-based fetcher: url, title, rss_summary, feed_category, published_date
        """
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        all_articles = []
        failed_count = 0

        for journal_name, issn in self.sources.items():
            logger.info(f"Fetching journal: {journal_name}")
            try:
                articles = self._fetch_single_journal(issn, journal_name, cutoff_date)
                all_articles.extend(articles)
                logger.info(f"Retrieved {len(articles)} articles from {journal_name}")
            except Exception as e:
                logger.error(f"Failed to fetch {journal_name}: {str(e)}")
                failed_count += 1
                continue

        if failed_count:
            logger.warning(f"{failed_count} of {len(self.sources)} journals failed to fetch")

        logger.info(f"Total articles retrieved: {len(all_articles)}")
        return all_articles

    def _fetch_single_journal(
        self,
        issn: str,
        journal_name: str,
        cutoff_date: str
    ) -> List[Dict]:
        """
        Fetch and parse works for a single journal ISSN.

        Args:
            issn: ISSN of the journal
            journal_name: Display name of the journal
            cutoff_date: Only return works created on/after this date (YYYY-MM-DD)

        Returns:
            List of parsed article dictionaries
        """
        params = {
            'filter': f'from-created-date:{cutoff_date},type:journal-article',
            'rows': '1000',
            'select': 'title,abstract,DOI,created',
            'mailto': self.mailto,
        }
        url = f"{self.BASE_URL}/{issn}/works?{urllib.parse.urlencode(params)}"
        headers = {
            'User-Agent': f'rss-digest/1.0 (mailto:{self.mailto})'
        }

        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))

        message = data.get('message', {})
        total_results = message.get('total-results', 0)
        items = message.get('items', [])

        if total_results > len(items):
            logger.warning(
                f"{journal_name}: total-results ({total_results}) exceeds "
                f"returned items ({len(items)}) - results may be truncated"
            )

        articles = []
        skipped = 0

        for item in items:
            doi = item.get('DOI')
            if not doi:
                logger.warning(f"{journal_name}: skipping item with no DOI")
                skipped += 1
                continue

            titles = item.get('title') or []
            title = _clean_text(titles[0]) if titles else ''
            if not title:
                logger.warning(f"{journal_name}: skipping item with no title (DOI={doi})")
                skipped += 1
                continue

            abstract = _clean_text(item.get('abstract', ''))

            # Crossref's deposit timestamp, not necessarily the journal's official
            # publication date - fine for an 8-day recency window, not authoritative.
            created = item.get('created', {})
            date_time_str = created.get('date-time')
            try:
                published_date = datetime.fromisoformat(date_time_str) if date_time_str else None
            except (ValueError, TypeError):
                logger.warning(f"{journal_name}: unparseable created date for DOI={doi}")
                published_date = None

            articles.append({
                'url': f'https://doi.org/{doi}',
                'title': title,
                'rss_summary': abstract,
                'feed_category': journal_name,
                'published_date': published_date,
            })

        if skipped:
            logger.warning(f"{journal_name}: skipped {skipped} of {len(items)} items")

        return articles


def test_journals(sources: Dict[str, str], mailto: str, days: int = 8) -> None:
    """
    Test function to verify Crossref fetching is working.

    Args:
        sources: Dictionary of journal names to ISSNs
        mailto: Contact email for Crossref's polite pool
        days: Number of days to look back
    """
    fetcher = CrossrefFetcher(sources, mailto=mailto)
    articles = fetcher.fetch_recent_articles(days)

    print(f"\n=== Crossref Fetcher Test Results ===")
    print(f"Total articles retrieved: {len(articles)}")
    print(f"\nSample articles:")

    for i, article in enumerate(articles[:5], 1):
        print(f"\n{i}. {article['title']}")
        print(f"   Feed: {article['feed_category']}")
        print(f"   Date: {article['published_date']}")
        print(f"   URL: {article['url']}")
        print(f"   Summary: {article['rss_summary'][:100]}...")


if __name__ == "__main__":
    import os
    import sys
    from dotenv import load_dotenv

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    load_dotenv()

    from config.feeds import CROSSREF_SOURCES

    mailto = os.getenv("FROM_EMAIL")
    if mailto:
        test_journals(CROSSREF_SOURCES, mailto=mailto)
    else:
        print("Please set FROM_EMAIL in .env file")
