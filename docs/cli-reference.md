# CLI reference

All commands are invoked as `uv run mblabelsite <command>`. Global options (listed in the README) go before the command name.

## Fetch commands

These commands query the MusicBrainz API. Each release requires at least two API calls (metadata + cover art), and requests are rate-limited to one per second, so large fetches can take several minutes.

### update

```
uv run mblabelsite update
```

Incremental update. Fetches the current release list for the label, then:

- Downloads metadata and cover art for any releases not yet in the cache
- Removes releases that no longer appear on the label
- Fetches artist info for any new artists
- Regenerates the full HTML site

This is the command you want for routine use. It only fetches what is new.

### refresh

```
uv run mblabelsite refresh [--resume RELEASE_ID]
```

Re-fetches metadata for every release on the label. Cover art is only downloaded if the file does not already exist locally. After fetching, the site is regenerated.

Use this when MusicBrainz data has been corrected (track listings, artist credits, etc.) and you want to pull in the changes without re-downloading all cover art.

**`--resume RELEASE_ID`**: Skip all releases up to and including the given ID. Use this to continue a failed run without re-processing releases that were already successfully fetched. The error message from a failed run tells you exactly which ID to pass.

### total-refresh

```
uv run mblabelsite total-refresh [--resume RELEASE_ID]
```

Re-fetches everything from scratch, including cover art. On a fresh run (without `--resume`), the entire cover art directory is deleted before fetching begins.

**`--resume RELEASE_ID`**: Same as `refresh --resume`, but also skips the cover art deletion step so that covers from the original run are preserved.

### generate

```
uv run mblabelsite generate
```

Regenerates all HTML from the SQLite cache without making any API calls. Use this after editing templates, input files, or user data (embeds, notes, rewrites) to see the changes reflected in the output.

### migrate

```
uv run mblabelsite migrate
```

One-time migration from the legacy flat-file cache (the old `data/releases/`, `data/artists/` files) to the SQLite database. You only need this if upgrading from the original `listMusic.py` version of the tool.

## Query commands

These commands read from the local cache and make no API calls.

### list-releases

```
uv run mblabelsite list-releases
```

Lists all cached releases, one per line, sorted by date descending:

```
2024 | Artist Name - Release Title [TTR001]
2023 | Other Artist - Another Release [TTR002] [IGNORED]
```

Releases marked as ignored show `[IGNORED]` at the end.

### show-release

```
uv run mblabelsite show-release "search term"
```

Shows full details for a release. The argument is a fuzzy search by title. If multiple releases match, you are prompted to choose. You can also pass a MusicBrainz release UUID directly.

Output includes: ID, artist credit, title, date, label, catalog number, slug, artist/remixer/mastering IDs, and the full track listing with durations.

### search

```
uv run mblabelsite search "query"
```

Searches releases by title (case-insensitive substring match). Returns a list in the same format as `list-releases`.

### list-artists

```
uv run mblabelsite list-artists
```

Lists all cached artists with their URL slug.

### show-artist

```
uv run mblabelsite show-artist "name"
```

Shows artist details (ID, name, slug) and lists all their releases, remixes, and mastering credits. The argument is a fuzzy search by name.

## Data manipulation commands

These commands modify user data stored in the SQLite database. Changes take effect the next time you run `generate`, `update`, `refresh`, or `total-refresh`.

All commands that accept a release or artist name perform fuzzy matching. If there are multiple matches, you are prompted to pick one. You can also pass a MusicBrainz UUID directly.

### Embeds

#### add-bandcamp

```
uv run mblabelsite add-bandcamp '<iframe ...></iframe>' "release title"
```

Associates a Bandcamp embed with a release. The first argument is the full embed code (the HTML iframe you get from Bandcamp's share/embed dialog). Quote it carefully since it contains HTML.

#### remove-bandcamp

```
uv run mblabelsite remove-bandcamp "release title"
```

Removes the Bandcamp embed from a release.

#### add-soundcloud

```
uv run mblabelsite add-soundcloud "https://soundcloud.com/..." "release title"
```

Associates a SoundCloud embed URL with a release. This is the URL used as the `src` of the SoundCloud iframe, not the page URL.

#### remove-soundcloud

```
uv run mblabelsite remove-soundcloud "release title"
```

Removes the SoundCloud embed from a release.

### Release notes

#### add-note

```
uv run mblabelsite add-note "release title" "Note text here"
```

Adds or replaces the release note. HTML is allowed in the note text.

#### remove-note

```
uv run mblabelsite remove-note "release title"
```

Removes the release note.

### URL slug overrides

By default, release and artist URLs are generated from the artist name and title (lowercased, spaces replaced with hyphens, special characters stripped). These commands let you override that.

#### set-rewrite

```
uv run mblabelsite set-rewrite "release title" "custom-slug"
```

Sets a custom URL slug for a release. The generated HTML will use `custom-slug.html` instead of the computed slug.

#### remove-rewrite

```
uv run mblabelsite remove-rewrite "release title"
```

Reverts a release to its computed slug.

#### set-artist-rewrite

```
uv run mblabelsite set-artist-rewrite "artist name" "custom-slug"
```

Sets a custom URL slug for an artist.

#### remove-artist-rewrite

```
uv run mblabelsite remove-artist-rewrite "artist name"
```

Reverts an artist to its computed slug.

### Ignored releases

Ignored releases are excluded from the homepage and artist pages. They remain in the database and their individual release pages are still generated, but they do not appear in any listing.

#### ignore-release

```
uv run mblabelsite ignore-release "release title"
```

#### unignore-release

```
uv run mblabelsite unignore-release "release title"
```

### Physical release info

Physical release info is HTML content describing physical media (vinyl, CD) for a release. It appears on the release page in a dedicated section.

#### set-physical

```
uv run mblabelsite set-physical "release title" "<p>Available on vinyl...</p>"
```

#### remove-physical

```
uv run mblabelsite remove-physical "release title"
```

### Display ordering

By default, artists and mastering engineers are listed in the order MusicBrainz returns them. These commands let you specify a custom display order.

#### set-artist-order

```
uv run mblabelsite set-artist-order "release title" "uuid1,uuid2,uuid3"
```

Takes a comma-separated list of MusicBrainz artist UUIDs. The artists will be displayed in that order on the release page.

#### set-mastering-order

```
uv run mblabelsite set-mastering-order "release title" "uuid1,uuid2"
```

Same as `set-artist-order`, but for mastering engineers.
