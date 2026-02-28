"""Data models for releases, artists, and tracks."""

from dataclasses import dataclass, field


@dataclass
class Track:
    position: int
    title: str
    length_ms: int = 0


@dataclass
class PurchaseLink:
    store_name: str
    url: str
    position: int


@dataclass
class Release:
    id: str
    artist_credit: str
    title: str
    date: str
    label: str = ""
    catno: str = ""
    artist_ids: list[str] = field(default_factory=list)
    remixer_ids: list[str] = field(default_factory=list)
    mastering_ids: list[str] = field(default_factory=list)
    cover_art_designer_ids: list[str] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    purchase_links: list[PurchaseLink] = field(default_factory=list)
    artist_credit_phrase: str = ""
    slug: str = ""

    def cleanup_title(self):
        """Replace smart quotes in title."""
        self.title = self.title.replace("\u201c", "&#8220;")
        self.title = self.title.replace("\u201d", "&#8221;")


@dataclass
class Artist:
    id: str
    name: str
    slug: str = ""
