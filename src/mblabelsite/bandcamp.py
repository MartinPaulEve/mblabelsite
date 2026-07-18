"""Build Bandcamp embed HTML from a public Bandcamp URL."""

import html
import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SEARCH_URL = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"

TRACK = "t"
ALBUM = "a"

_PATH_TYPES = {"track": TRACK, "album": ALBUM}

# Player parameters differ between single tracks and albums: albums get the
# taller player with a visible tracklist.
_PLAYER = {
    TRACK: {"key": "track", "height": "120px", "tracklist": "false"},
    ALBUM: {"key": "album", "height": "470px", "tracklist": "true"},
}


class BandcampError(Exception):
    """Raised when a Bandcamp URL cannot be turned into an embed."""


def parse_bandcamp_url(url: str) -> tuple[str, str]:
    """Return (item_type, slug) for a Bandcamp track or album URL."""
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise BandcampError(f"Not a valid URL: {url}")
    host = parsed.netloc.lower()
    if not (host == "bandcamp.com" or host.endswith(".bandcamp.com")):
        raise BandcampError(f"Not a Bandcamp URL: {url}")

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 2 or parts[0] not in _PATH_TYPES:
        raise BandcampError(f"Not a Bandcamp track or album URL: {url}")

    return _PATH_TYPES[parts[0]], parts[1]


def build_embed(item_type: str, item_id: int, url: str, title: str, artist: str) -> str:
    """Return the iframe embed HTML for a Bandcamp item."""
    player = _PLAYER[item_type]
    src = (
        f"https://bandcamp.com/EmbeddedPlayer/{player['key']}={item_id}"
        f"/size=large/bgcol=ffffff/linkcol=0687f5"
        f"/tracklist={player['tracklist']}/artwork=small/transparent=true/"
    )
    link_text = html.escape(f"{title} by {artist}")
    return (
        f'<iframe style="border: 0; width: 100%; height: {player["height"]};" '
        f'src="{src}" seamless>'
        f'<a href="{html.escape(url, quote=True)}">{link_text}</a></iframe>'
    )


def _normalise(url: str) -> str:
    """Reduce a Bandcamp URL to a comparable host+path form."""
    parsed = urlparse(url.strip())
    return f"{parsed.netloc.lower()}{parsed.path.rstrip('/').lower()}"


def _search(text: str, item_type: str) -> list[dict]:
    """Query Bandcamp's public autocomplete API."""
    payload = json.dumps(
        {
            "search_text": text,
            "search_filter": item_type,
            "full_page": False,
            "fan_id": None,
        }
    ).encode()
    request = urllib.request.Request(
        SEARCH_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise BandcampError(f"Could not reach Bandcamp: {exc}") from exc
    return data.get("auto", {}).get("results", []) or []


def lookup_item(url: str, search=None) -> dict:
    """Resolve a Bandcamp URL to {item_type, item_id, title, artist}."""
    search = search or _search
    item_type, slug = parse_bandcamp_url(url)
    target = _normalise(url)
    artist_slug = urlparse(url.strip()).netloc.split(".")[0]
    words = slug.replace("-", " ")

    for query in (words, f"{words} {artist_slug}"):
        for result in search(query, item_type):
            if _normalise(result.get("item_url_path", "")) == target:
                return {
                    "item_type": item_type,
                    "item_id": result["id"],
                    "title": result["name"],
                    "artist": result["band_name"],
                }
        logger.debug("No Bandcamp match for query %r", query)

    raise BandcampError(
        f"Could not find {url} on Bandcamp. "
        "If it is private or unlisted, use add-bandcamp-html instead."
    )


def embed_from_url(url: str, search=None) -> str:
    """Return embed HTML for a Bandcamp track or album URL."""
    item = lookup_item(url, search=search)
    return build_embed(
        item["item_type"], item["item_id"], url, item["title"], item["artist"]
    )
