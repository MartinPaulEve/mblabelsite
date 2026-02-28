"""Pydantic models for parsing MusicBrainz API responses."""

from pydantic import BaseModel, Field


class MBArtistRef(BaseModel):
    id: str
    name: str


class MBArtistCredit(BaseModel):
    artist: MBArtistRef


class MBArtistRelation(BaseModel):
    type: str
    artist: MBArtistRef


class MBUrlRelation(BaseModel):
    type: str
    target: str


class MBRecording(BaseModel):
    title: str
    length: int | None = None
    artist_credit_phrase: str = Field(default="", alias="artist-credit-phrase")
    artist_relation_list: list[MBArtistRelation] = Field(
        default_factory=list, alias="artist-relation-list"
    )


class MBTrack(BaseModel):
    recording: MBRecording


class MBMedium(BaseModel):
    track_list: list[MBTrack] = Field(default_factory=list, alias="track-list")


class MBLabelInfo(BaseModel):
    label: MBArtistRef | None = None
    catalog_number: str | None = Field(default=None, alias="catalog-number")


class MBRelease(BaseModel):
    """Parsed MusicBrainz release response."""

    id: str
    title: str
    date: str = ""
    artist_credit_phrase: str = Field(default="", alias="artist-credit-phrase")
    artist_credit: list[MBArtistCredit | str] = Field(
        default_factory=list, alias="artist-credit"
    )
    artist_relation_list: list[MBArtistRelation] = Field(
        default_factory=list, alias="artist-relation-list"
    )
    url_relation_list: list[MBUrlRelation] = Field(
        default_factory=list, alias="url-relation-list"
    )
    medium_list: list[MBMedium] = Field(default_factory=list, alias="medium-list")
    label_info_list: list[MBLabelInfo] = Field(
        default_factory=list, alias="label-info-list"
    )

    model_config = {"populate_by_name": True}


class MBBrowseRelease(BaseModel):
    """A release entry from browse results (minimal info)."""

    id: str
    date: str = ""


class MBBrowseResult(BaseModel):
    """Result from browsing releases."""

    release_list: list[MBBrowseRelease] = Field(
        default_factory=list, alias="release-list"
    )
