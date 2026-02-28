# mblabelsite

A static site generator for music record labels. It pulls release metadata and cover art from the MusicBrainz API, caches everything locally in SQLite, and generates a complete HTML website with pages for each release and artist.

Built for [tici taci records](https://ticitaci.com), but adaptable to any MusicBrainz label by changing the label ID in `pyproject.toml`. The `input/` directory included in this repository is the tici taci configuration and serves as a reference for setting up your own label.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)

## Installation

```
git clone <repo-url>
cd musicBrainzLabel
uv sync
```

## Quick start

Fetch all releases for the label from MusicBrainz and generate the site:

```
uv run mblabelsite update
```

This does the following:

1. Queries MusicBrainz for all releases on the label
2. Downloads metadata and cover art for any new releases
3. Removes releases that have been deleted from MusicBrainz
4. Fetches artist information for any new artists
5. Generates HTML pages into the `output/` directory

For subsequent runs, `update` only fetches new or changed releases, so it is fast.

## Common workflows

**Regenerate the site without fetching anything:**

```
uv run mblabelsite generate
```

**Re-fetch all release metadata (keeping existing cover art):**

```
uv run mblabelsite refresh
```

**Re-fetch everything, including cover art:**

```
uv run mblabelsite total-refresh
```

**Add a SoundCloud player to a release:**

```
uv run mblabelsite add-soundcloud "https://soundcloud.com/..." "release title"
```

**Add a Bandcamp player to a release:**

```
uv run mblabelsite add-bandcamp '<iframe ...></iframe>' "release title"
```

**Override a release's URL slug:**

```
uv run mblabelsite set-rewrite "release title" "custom-slug"
```

## Resuming failed fetches

Network errors or API failures during `refresh` or `total-refresh` can interrupt a long-running fetch. When this happens, the error message tells you the last successfully processed release ID:

```
Error: Cover art download failed for release abc123.
Run 'mblabelsite refresh --resume def456' to resume.
```

Use `--resume` to skip already-processed releases and continue where you left off:

```
uv run mblabelsite refresh --resume def456
uv run mblabelsite total-refresh --resume def456
```

When resuming `total-refresh`, the cover art directory is not wiped again, so covers from the original run are preserved.

## Global options

These apply to all commands:

| Option | Default | Description |
|---|---|---|
| `--label` | tici taci label ID | MusicBrainz label UUID |
| `--data-dir` | `data` | Directory for the SQLite cache |
| `--input-dir` | `input` | Directory for user-provided override files |
| `--output-dir` | `output` | Directory for generated HTML |
| `--template-dir` | `templates` | Directory for HTML templates |
| `--debug / --no-debug` | `--no-debug` | Enable verbose debug logging |

## Further documentation

- [CLI reference](docs/cli-reference.md) -- full list of all commands, arguments, and options
- [Input files](docs/input-files.md) -- file formats for manual overrides (rewrites, embeds, notes, images)
- [Templates](docs/templates.md) -- how the template system works and available placeholders

## Project structure

```
src/mblabelsite/       Source code
  cli.py               Click CLI entry point
  fetcher.py           Fetch orchestration (update/refresh/total-refresh)
  generator.py         HTML generation from cached data
  mb_client.py         MusicBrainz API wrapper with rate limiting
  mb_models.py         Pydantic models for MusicBrainz JSON responses
  models.py            Internal data models (Release, Artist, Track)
  database.py          SQLite database layer
  config.py            Constants (label ID, excluded IDs, store names)
  slug.py              URL slug generation and sanitization
  templates.py         Template loading
  migrate.py           One-time migration from legacy flat-file cache
input/                 User-provided override files (included as a reference example)
templates/             HTML templates
data/                  SQLite cache (cache.db)
output/                Generated HTML site
tests/                 Test suite
```

## Output structure

The generated site looks like this:

```
output/
  index.html                     Homepage with cover art grid
  css/
    music.css                    Homepage styles
    release.css                  Release and artist page styles
  images/
    site/header.png, favicon.png
    covers/{release-uuid}        Cover art images
    artists/{artist-uuid}        Artist photos
    physical/{release-uuid}      Physical media photos
  releases/
    {release-uuid}.html          Release page (by ID)
    {release-slug}.html          Release page (by slug)
  artists/
    {artist-uuid}.html           Artist page (by ID)
    {artist-slug}.html           Artist page (by slug)
```

Each release and artist gets two HTML files: one named by UUID (for stable linking) and one named by slug (for readable URLs).

## Running tests

```
uv run pytest -v
```

### Validation tests

The test suite includes validation tests (`tests/test_validation.py`) that compare generated HTML output against a known-good reference in a `validation/` directory. This directory is not distributed with the repository because it contains large binary cover art images (~75MB).

When `validation/` is absent, these tests are automatically skipped — the rest of the test suite runs normally.

To create the validation directory for your own label:

1. Run a full fetch and generate cycle: `uv run mblabelsite update`
2. Copy the output as your reference: `cp -r output validation`
3. Run the full test suite: `uv run pytest -v`

The validation tests verify that the generator produces identical HTML to the reference, catching regressions in template rendering, slug generation, and cover art handling.

## Linting

```
uv run ruff check src/ tests/
```
