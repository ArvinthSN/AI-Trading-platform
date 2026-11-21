import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.core.errors import ProviderUnavailable

logger = logging.getLogger(__name__)
MAX_FEED_BYTES = 2_000_000


@dataclass(frozen=True)
class RssArticle:
    id: str
    headline: str
    source: str
    published_at: datetime
    original_url: str


class RssNewsSource:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch(
        self,
        url: str,
        category: str,
        limit: int = 20,
    ) -> tuple[str, datetime, list[RssArticle]]:
        try:
            response = await self._client.get(
                url,
                headers={"Accept": "application/rss+xml, application/atom+xml, application/xml"},
            )
        except httpx.HTTPError as error:
            logger.warning("rss_fetch_failed category=%s error=%s", category, type(error).__name__)
            raise ProviderUnavailable(category, "News provider could not be reached.") from error
        if response.status_code == 429:
            from app.core.errors import ProviderRateLimited

            raise ProviderRateLimited(category, response.headers.get("Retry-After"))
        if response.is_error:
            raise ProviderUnavailable(
                category, f"News provider returned HTTP {response.status_code}."
            )
        if len(response.content) > MAX_FEED_BYTES:
            raise ProviderUnavailable(category, "News feed exceeded the maximum response size.")
        try:
            root = ElementTree.fromstring(response.content)
        except DefusedXmlException as error:
            raise ProviderUnavailable(category, "News provider returned unsafe XML.") from error
        except ElementTree.ParseError as error:
            raise ProviderUnavailable(category, "News provider returned invalid XML.") from error
        channel = root.find("channel")
        if channel is None:
            channel = root
        feed_source = _text(channel, "title") or category
        now = datetime.now(UTC)
        items: list[RssArticle] = []
        for item in channel.findall("item")[:limit]:
            title = _text(item, "title")
            link = _text(item, "link")
            date_text = _text(item, "pubDate") or _text(item, "published")
            if not title or not link or not date_text:
                continue
            try:
                published = parsedate_to_datetime(date_text)
                if published.tzinfo is None:
                    continue
                published = published.astimezone(UTC)
                source_name = _text(item, "source") or feed_source
                identifier = hashlib.sha256(f"{link}|{published.isoformat()}".encode()).hexdigest()[
                    :20
                ]
                items.append(
                    RssArticle(
                        id=identifier,
                        headline=title,
                        source=source_name,
                        published_at=published,
                        original_url=link,
                    )
                )
            except (TypeError, ValueError):
                logger.warning("rss_item_invalid category=%s", category)
        return feed_source, now, items


def _text(element: Element, name: str) -> str | None:
    child = element.find(name)
    if child is None or child.text is None:
        return None
    return child.text.strip() or None
