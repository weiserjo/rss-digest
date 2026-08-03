"""
Main Orchestration Script
Simplified workflow: Fetch articles from Crossref → Generate AI digest → Send email
No database dependencies - completely stateless.
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import load_dotenv

from crossref_fetcher import CrossrefFetcher
from llm_processor import LLMProcessor
from email_sender import EmailSender
from config.feeds import CROSSREF_SOURCES, DIGEST_GENERATION_PROMPT


# Configure logging
def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    # Windows consoles default to cp1252, which can't encode characters
    # like unicode checkmarks or dashes that show up in log messages.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('digest.log', encoding='utf-8')
        ]
    )

    # These libraries' DEBUG logs dump the full request (including the whole
    # prompt) even under our own --verbose; keep them quiet regardless.
    for noisy_logger in ("openai", "httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


def _sample_across_feeds(articles: List[Dict], limit: int) -> List[Dict]:
    """
    Take up to `limit` articles round-robin across feed categories, so a
    --test slice covers multiple feeds instead of one feed's oldest items.
    """
    by_feed: Dict[str, List[Dict]] = {}
    for article in articles:
        by_feed.setdefault(article['feed_category'], []).append(article)

    sampled = []
    while len(sampled) < limit and any(by_feed.values()):
        for feed_articles in by_feed.values():
            if feed_articles:
                sampled.append(feed_articles.pop(0))
                if len(sampled) >= limit:
                    break
    return sampled


class DigestOrchestrator:
    """Main orchestrator for the digest system."""

    def __init__(
        self,
        openai_api_key: str,
        smtp_password: str,
        from_email: str,
        recipient_email: str,
        openai_base_url: Optional[str] = None
    ):
        """
        Initialize the orchestrator with all necessary credentials.

        Args:
            openai_api_key: OpenAI-compatible API key
            smtp_password: Google App Password for SMTP authentication
            from_email: Sender email address (Gmail address)
            recipient_email: Email address to send digest to
            openai_base_url: Base URL for OpenAI-compatible API (optional)
        """
        self.crossref_fetcher = CrossrefFetcher(CROSSREF_SOURCES, mailto=from_email)
        self.llm_processor = LLMProcessor(openai_api_key, base_url=openai_base_url)
        self.email_sender = EmailSender(smtp_password, from_email)
        self.recipient_email = recipient_email

        logger.info("Digest orchestrator initialized")

    def generate_and_send_digest(
        self,
        days: int = 8,
        dry_run: bool = False,
        save_html: bool = True,
        limit: Optional[int] = None
    ) -> bool:
        """
        Complete workflow: Fetch articles, generate digest, and send email.

        Args:
            days: Number of days to look back for articles
            dry_run: If True, generate but don't send email
            save_html: If True, save digest as HTML file
            limit: Limit number of articles (for testing)

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("STARTING DIGEST WORKFLOW")
        logger.info("=" * 60)

        try:
            # Step 1: Fetch articles from Crossref
            logger.info(f"\n[STEP 1] Fetching articles from past {days} days")
            articles = self.crossref_fetcher.fetch_recent_articles(days)

            if not articles:
                logger.warning("No articles fetched")
                return False

            logger.info(f"✓ Fetched {len(articles)} articles")

            # Limit articles if specified (for testing)
            if limit:
                articles = _sample_across_feeds(articles, limit)
                logger.info(f"Limited to {limit} articles for testing (sampled across feeds)")

            # Step 2: Generate digest with LLM
            logger.info(f"\n[STEP 2] Generating digest from {len(articles)} articles")

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

            # Generate digest HTML in a single LLM call
            digest_html = self.llm_processor.generate_digest_from_articles(
                articles,
                DIGEST_GENERATION_PROMPT,
                date_range
            )

            if not digest_html:
                logger.error("Failed to generate digest")
                return False

            logger.info("✓ Digest generated successfully")

            # Log token usage
            usage = self.llm_processor.get_token_usage_summary()
            logger.info(f"Token usage: {usage['total_tokens']} tokens")

            # Step 3: Save HTML if requested
            if save_html:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filepath = f"digest_{timestamp}.html"
                self.email_sender.save_digest_html(digest_html, date_range, filepath)
                logger.info(f"✓ Digest saved to {filepath}")

            # Step 3: Send email (unless dry run)
            if not dry_run:
                logger.info("\n[STEP 3] Sending digest email")
                success = self.email_sender.send_digest(
                    recipient_email=self.recipient_email,
                    digest_html=digest_html,
                    date_range=date_range,
                    article_count=len(articles),
                    template_path="templates/email_template.html"
                )

                if success:
                    logger.info("✓ Digest sent successfully")
                    logger.info("\n" + "=" * 60)
                    logger.info("WORKFLOW COMPLETE")
                    logger.info("=" * 60)
                    logger.info(f"\nSummary:")
                    logger.info(f"  Articles processed: {len(articles)}")
                    logger.info(f"  Date range: {date_range}")
                    logger.info(f"  Total tokens: {usage['total_tokens']}")
                    return True
                else:
                    logger.error("Failed to send digest email")
                    return False
            else:
                logger.info("\nDry run mode - email not sent")
                logger.info("✓ Digest saved to HTML file")
                logger.info("\n" + "=" * 60)
                logger.info("WORKFLOW COMPLETE (DRY RUN)")
                logger.info("=" * 60)
                logger.info(f"\nSummary:")
                logger.info(f"  Articles processed: {len(articles)}")
                logger.info(f"  Date range: {date_range}")
                logger.info(f"  Total tokens: {usage['total_tokens']}")
                return True

        except Exception as e:
            logger.error(f"Error in workflow: {str(e)}", exc_info=True)
            return False


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="RSS Weekly Digest - Automated journal monitoring and digest generation"
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: process only 5 articles'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode: generate digest but do not send email'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=8,
        help='Number of days to look back for articles (default: 8)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save digest as HTML file'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Load environment variables
    load_dotenv()

    # Check required environment variables
    required_vars = [
        'OPENAI_API_KEY',
        'LLM_MODEL',
        'SMTP_PASSWORD',
        'FROM_EMAIL',
        'RECIPIENT_EMAIL'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file")
        sys.exit(1)

    # Initialize orchestrator
    orchestrator = DigestOrchestrator(
        openai_api_key=os.getenv('OPENAI_API_KEY'),
        smtp_password=os.getenv('SMTP_PASSWORD'),
        from_email=os.getenv('FROM_EMAIL'),
        recipient_email=os.getenv('RECIPIENT_EMAIL'),
        openai_base_url=os.getenv('OPENAI_BASE_URL')
    )

    # Run workflow
    limit = 5 if args.test else None
    success = orchestrator.generate_and_send_digest(
        days=args.days,
        dry_run=args.dry_run,
        save_html=not args.no_save,
        limit=limit
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
