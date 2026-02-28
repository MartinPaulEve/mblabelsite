# Templates

The site is generated using a simple string-replacement template system. Templates are plain HTML files with placeholder tokens that get replaced during generation. There is no Jinja2 or other template engine involved.

## Placeholder syntax

Placeholders use two styles:

- `[NAME]` for single-value replacements (artist name, title, embed URL, etc.)
- `[[NAME]]` for block-level replacements (lists of releases, notes sections, etc.)

If a placeholder's data is empty or missing, the entire containing template section is omitted from the output.

## Template files

All templates live in the `templates/` directory.

### Homepage

**`template`** generates `index.html`. Contains a single placeholder:

- `[CONTENTS]` -- replaced with a grid of cover art thumbnails linking to release pages.

### Release pages

**`template_release`** is the default template for all release pages. Placeholders:

| Placeholder | Content |
|---|---|
| `[ARTIST]` | Artist credit string (plain text) |
| `[TITLE]` | Release title |
| `[YEAR]` | Four-digit year from the release date |
| `[CATNO]` | Catalog number |
| `[RELEASEID]` | MusicBrainz release UUID |
| `[COVERIMAGE]` | Path to the cover art image file |
| `[ARTISTS]` | Linked artist names (with custom ordering if set) |
| `[REMIXERS]` | "Remixed by" section with linked names, omitted if none |
| `[MASTERING]` | "Mastered by" section with linked names, omitted if none |
| `[COVERARTDESIGNER]` | "Cover art by" section with linked names, omitted if none |
| `[PURCHASEINFO]` | Purchase links (Bandcamp, Beatport, Juno, Traxsource) |
| `[TRACKS]` | Numbered track listing with durations |
| `[SOUNDCLOUD]` | SoundCloud player iframe, omitted if no embed set |
| `[BANDCAMP]` | Bandcamp player embed, omitted if no embed set |
| `[PHYSICAL]` | Physical release info, omitted if none |
| `[NOTES]` | Release notes, omitted if none |
| `[[IMAGEHEIGHT]]` | Cover art image height in pixels |
| `[[IMAGEWIDTH]]` | Cover art image width in pixels |

### Per-release template overrides

To use a custom template for a specific release, create a file at:

```
templates/releases/{release-uuid}.template
```

This file uses the same placeholders as `template_release`. It completely replaces the default template for that release.

### Artist pages

**`artist`** is the template for artist pages. Placeholders:

| Placeholder | Content |
|---|---|
| `[ARTIST]` | Artist name |
| `[ARTISTID]` | MusicBrainz artist UUID |
| `[[RELEASES]]` | List of the artist's releases (as cover art links) |
| `[[REMIXES]]` | List of releases the artist remixed |
| `[[MASTERS]]` | List of releases the artist mastered |
| `[[IMAGEHEIGHT]]` | Artist image height in pixels |
| `[[IMAGEWIDTH]]` | Artist image width in pixels |

### Sub-templates

These are used internally by the generator to build sections of release and artist pages:

| File | Purpose | Key placeholder |
|---|---|---|
| `template_artists` | Artist name link (used for building artist lists) | `[ARTIST]` |
| `template_tracks` | Track listing wrapper | `[TRACKS]` |
| `template_purchase` | Purchase links wrapper | `[PURCHASELINKS]` |
| `template_soundcloud` | SoundCloud iframe | `[EMBEDURL]` |
| `template_bandcamp` | Bandcamp embed wrapper | `[EMBEDURL]` |
| `template_notes` | Release notes wrapper | `[[NOTES]]` |
| `template_physical` | Physical info wrapper | `[[PHYSICAL]]` |
| `artist_releases` | "Releases" section heading on artist pages | `[[RELEASES]]` |
| `artist_remixes` | "Remixes" section heading on artist pages | `[[RELEASES]]` |
| `artist_masters` | "Mastering" section heading on artist pages | `[[RELEASES]]` |

## Editing templates

Templates are plain HTML. Edit them directly, then run `uv run mblabelsite generate` to rebuild the site.

The static assets `music.css`, `release.css`, `header.png`, and `favicon.png` live in the `input/` directory and are copied to `output/css/` and `output/images/site/` during generation. Edit them in place and regenerate.
