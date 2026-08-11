"""
LLM Processor Module
Handles digest generation directly from raw articles using OpenAI-compatible APIs.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from openai import OpenAI
from openai import RateLimitError, APIError, APIConnectionError

logger = logging.getLogger(__name__)

# Linear model fit to real runs (with reasoning_effort="low"):
#   5 articles   -> 2,585 completion tokens
#   921 articles -> 24,586 completion tokens
# tokens_needed = TOKENS_BASE + TOKENS_PER_ARTICLE * article_count
TOKENS_BASE = 2465
TOKENS_PER_ARTICLE = 24
MAX_TOKENS_SAFETY_MARGIN = 1.3
MAX_TOKENS_FLOOR = 8000
MAX_TOKENS_CEILING = 64000


def _estimate_max_tokens(article_count: int) -> int:
    """
    Estimate a safe max_tokens budget from article count, based on the
    linear model above. Both data points are true natural-completion values
    (finish_reason=stop, not truncated), so the margin only needs to cover
    run-to-run variance and extrapolation beyond the observed range, not
    correct for a bad fit.
    """
    estimated = TOKENS_BASE + TOKENS_PER_ARTICLE * article_count
    with_margin = round(estimated * MAX_TOKENS_SAFETY_MARGIN)
    clamped = min(max(with_margin, MAX_TOKENS_FLOOR), MAX_TOKENS_CEILING)

    if with_margin > MAX_TOKENS_CEILING:
        logger.warning(
            f"max_tokens estimate for {article_count} articles ({with_margin}) exceeds "
            f"the {MAX_TOKENS_CEILING} ceiling - capping it, which reduces or eliminates "
            "the safety margin. Consider raising MAX_TOKENS_CEILING."
        )

    return clamped


class LLMProcessor:
    """Processes articles using LLM via OpenAI-compatible APIs."""

    def __init__(self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize LLM processor.

        Args:
            api_key: OpenAI-compatible API key
            model: Model to use (optional, will use LLM_MODEL env var or default)
            base_url: Base URL for OpenAI-compatible API (optional, defaults to OpenAI API)
        """
        import os
        if model is None:
            model = os.getenv("LLM_MODEL")

        # Only pass base_url if it's provided and not empty
        if base_url:
            self.client = OpenAI(
                base_url=base_url,
                api_key=api_key
            )
            logger.info(f"LLM Processor initialized with model: {model}, base_url: {base_url}")
        else:
            self.client = OpenAI(
                api_key=api_key
            )
            logger.info(f"LLM Processor initialized with model: {model}")

        self.model = model
        self.total_tokens_used = 0

    def generate_digest_from_articles(
        self,
        articles: List[Dict],
        prompt_template: str,
        date_range: str
    ) -> Optional[str]:
        """
        Generate digest HTML directly from raw RSS articles in a single LLM call.

        Args:
            articles: List of raw article dictionaries from RSS feeds
            prompt_template: Prompt template for digest generation
            date_range: String describing the date range (e.g., "Jan 15-21, 2025")

        Returns:
            HTML formatted digest or None if failed
        """
        try:
            if not articles:
                logger.warning("No articles provided for digest generation")
                return None

            # Format article list for prompt
            article_list = self._format_raw_articles_for_prompt(articles)

            # Format prompt
            prompt = prompt_template.format(
                article_count=len(articles),
                article_list=article_list,
                date_range=date_range
            )

            logger.info(f"Generating digest for {len(articles)} articles")

            max_tokens = _estimate_max_tokens(len(articles))
            logger.info(f"Using max_tokens={max_tokens} for {len(articles)} articles")

            # reasoning_effort="low" keeps this triage/summarization task from
            # burning its token budget on reasoning depth it doesn't need,
            # leaving more of max_tokens available for the actual digest text.
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a skilled editor creating weekly digests for the audience and topic described in the user prompt. Follow its instructions precisely and produce a comprehensive digest in clean, semantic HTML."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                extra_body={"reasoning_effort": "low"}
            )

            # Track token usage
            if hasattr(response, 'usage'):
                tokens = response.usage.total_tokens
                self.total_tokens_used += tokens
                logger.info(f"Digest generation tokens used: {tokens}")

            choice = response.choices[0]
            digest_html = (choice.message.content or "").strip()

            if not digest_html:
                logger.error(
                    f"LLM returned empty content (finish_reason={choice.finish_reason}). "
                    "This usually means max_tokens was hit before any visible output was "
                    "written (e.g. spent on reasoning) - consider raising max_tokens further."
                )
                return None

            logger.info("Successfully generated digest")
            return digest_html

        except RateLimitError as e:
            logger.warning(f"Rate limit hit (429 Too Many Requests) during digest generation.")
            logger.debug(f"Rate limit error details: {str(e)}")
            return None
        except APIConnectionError as e:
            logger.error(f"API connection error during digest generation: {str(e)}")
            return None
        except APIError as e:
            logger.error(f"API error during digest generation: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error generating digest: {str(e)}")
            return None

    def _format_raw_articles_for_prompt(self, articles: List[Dict]) -> str:
        """
        Format raw RSS articles into a readable list for the LLM prompt.

        Args:
            articles: List of raw article dictionaries from RSS feeds

        Returns:
            Formatted string with article details
        """
        formatted = []

        for i, article in enumerate(articles, 1):
            # Format published date
            pub_date = article.get('published_date')
            if isinstance(pub_date, datetime):
                pub_date_str = pub_date.strftime('%Y-%m-%d')
            else:
                pub_date_str = str(pub_date) if pub_date else 'Unknown'

            article_text = f"""
Article {i}:
Title: {article.get('title', 'Unknown')}
URL: {article.get('url', 'Unknown')}
Feed: {article.get('feed_category', 'Unknown')}
Published: {pub_date_str}
Summary: {article.get('rss_summary', 'No summary available')}
"""
            formatted.append(article_text.strip())

        return "\n\n---\n\n".join(formatted)

    def get_token_usage_summary(self) -> Dict:
        """
        Get summary of token usage.

        Returns:
            Dictionary with token usage statistics
        """
        return {
            'total_tokens': self.total_tokens_used
        }


def test_llm(api_key: str, base_url: Optional[str] = None) -> None:
    """
    Test LLM processor functionality.

    Args:
        api_key: OpenAI-compatible API key
        base_url: Base URL for OpenAI-compatible API (optional)
    """
    processor = LLMProcessor(api_key, base_url=base_url)

    print("\n=== LLM Processor Test ===")
    print(f"Using model: {processor.model}")

    # Test digest generation from raw articles
    test_articles = [
        {
            'title': 'Europe\'s economy faces headwinds from energy crisis',
            'rss_summary': 'Rising energy costs and supply chain disruptions continue to challenge European economies, with Germany and France showing slowest growth in years.',
            'feed_category': 'Europe',
            'published_date': datetime(2025, 1, 20),
            'url': 'https://example.com/article1'
        },
        {
            'title': 'ECB signals potential rate cuts',
            'rss_summary': 'European Central Bank hints at easing monetary policy as inflation shows signs of cooling.',
            'feed_category': 'Finance & Economics',
            'published_date': datetime(2025, 1, 21),
            'url': 'https://example.com/article2'
        }
    ]

    from config.feeds import DIGEST_GENERATION_PROMPT

    result = processor.generate_digest_from_articles(
        test_articles,
        DIGEST_GENERATION_PROMPT,
        "Jan 15-21, 2025"
    )

    if result:
        print("\nDigest Generated Successfully!")
        print(f"Length: {len(result)} characters")
    else:
        print("\nDigest generation failed")

    # Print token usage
    usage = processor.get_token_usage_summary()
    print(f"\nToken Usage:")
    for key, value in usage.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if api_key:
        test_llm(api_key, base_url)
    else:
        print("Please set OPENAI_API_KEY in .env file")
