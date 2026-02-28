# Input files

The `input/` directory contains user-provided files that supplement or replace data fetched from MusicBrainz. It holds two kinds of content:

- **Data files** (rewrites, embeds, notes, ordering, ignore) — imported into the SQLite database by `mblabelsite migrate`. After migration, this data lives in the database and these files are not read again. Use CLI commands to make changes going forward.
- **Images and static assets** (artist photos, physical release photos, CSS, favicon, header) — copied to the output directory on every `mblabelsite generate` run. These are always read from `input/`.

The `input/` directory included in this repository is the one used by [tici taci records](https://ticitaci.com) and serves as a reference example. To set up the system for your own label, create your own `input/` directory following the structure described below.

You can manage most data through CLI commands (see [CLI reference](cli-reference.md)), but the files can also be edited by hand. Files are named by MusicBrainz UUID and use short file extensions.

## File reference

### URL slug rewrites

**Directory:** `input/rewrites/`
**Extension:** `.rewrite`
**CLI equivalent:** `set-rewrite` / `remove-rewrite`

Each file contains a single line: the custom URL slug for a release. This overrides the auto-generated slug (which is derived from the artist name and title).

Example: `input/rewrites/3ba21ea2-3ff4-41b6-991e-6bd4d26ab223.rewrite`
```
duncan-gray-the-malcontent-vol-2
```

Without this file, the slug would be computed automatically. Use rewrites when the auto-generated slug is ugly, ambiguous, or when you want to preserve a specific URL after metadata changes.

### Artist slug rewrites

**Directory:** `input/artist_rewrites/`
**Extension:** `.rewrite`
**CLI equivalent:** `set-artist-rewrite` / `remove-artist-rewrite`

Same as release rewrites, but for artist page URLs.

Example: `input/artist_rewrites/abc12345-...rewrite`
```
future-bones
```

### SoundCloud embeds

**Directory:** `input/soundcloud/`
**Extension:** `.soundcloud`
**CLI equivalent:** `add-soundcloud` / `remove-soundcloud`

Each file contains a single line: the SoundCloud embed URL. This is the URL used as the `src` attribute of the SoundCloud iframe player, not the regular SoundCloud page URL.

Example: `input/soundcloud/3ba21ea2-3ff4-41b6-991e-6bd4d26ab223.soundcloud`
```
https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/123456789
```

To get this URL, use SoundCloud's embed/share dialog and extract the `src` from the generated iframe.

### Bandcamp embeds

**Directory:** `input/bandcamp/`
**Extension:** `.bandcamp`
**CLI equivalent:** `add-bandcamp` / `remove-bandcamp`

Each file contains the full Bandcamp embed HTML (typically an iframe). This is inserted directly into the release page.

Example: `input/bandcamp/3ba21ea2-3ff4-41b6-991e-6bd4d26ab223.bandcamp`
```html
<iframe style="border: 0; width: 100%; height: 120px;" src="https://bandcamp.com/EmbeddedPlayer/album=123456789/size=large/bgcol=ffffff/linkcol=0687f5/tracklist=false/artwork=small/transparent=true/" seamless><a href="https://artist.bandcamp.com/album/title">Title by Artist</a></iframe>
```

### Release notes

**Directory:** `input/notes/`
**Extension:** `.note`
**CLI equivalent:** `add-note` / `remove-note`

Free-form text (HTML allowed) displayed on the release page. Can be multiple lines.

Example: `input/notes/3ba21ea2-3ff4-41b6-991e-6bd4d26ab223.note`
```
Originally released as a limited run of 300 copies.
```

### Physical release info

**Directory:** `input/physical/`
**Extension:** `.physical`
**CLI equivalent:** `set-physical` / `remove-physical`

HTML content describing physical media (vinyl, CD, cassette) for a release. Appears in a dedicated section on the release page.

Example: `input/physical/3ba21ea2-3ff4-41b6-991e-6bd4d26ab223.physical`
```html
<p>12" vinyl, limited to 200 copies. Available from <a href="https://...">the shop</a>.</p>
```

### Artist display ordering

**Directory:** `input/artist_ordering/`
**Extension:** `.order`
**CLI equivalent:** `set-artist-order`

Controls the display order of artists on a release page. Each line is a MusicBrainz artist UUID. Artists are displayed in the order they appear in the file.

Example: `input/artist_ordering/3ba21ea2-3ff4-41b6-991e-6bd4d26ab223.order`
```
d4f7b9a1-1234-5678-abcd-ef0123456789
a1b2c3d4-5678-9abc-def0-123456789abc
```

Without this file, artists are displayed in whatever order MusicBrainz returns them.

### Mastering display ordering

**Directory:** `input/mastering_ordering/`
**Extension:** `.order`
**CLI equivalent:** `set-mastering-order`

Same as artist ordering, but controls the display order of mastering engineers on a release page.

### Ignored releases

**Directory:** `input/ignore/`
**Extension:** `.ignore`
**CLI equivalent:** `ignore-release` / `unignore-release`

Empty files. The presence of the file marks the release as ignored. Ignored releases are excluded from the homepage and artist pages, but their individual release pages are still generated.

Example: `input/ignore/3ba21ea2-3ff4-41b6-991e-6bd4d26ab223.ignore`
(empty file)

### Artist images

**Directory:** `input/images/artists/`
**No extension**
**No CLI equivalent** (manual only)

Image files (PNG or JPG) named by artist UUID. These are copied to the output directory and displayed on artist pages. A file named `generic` serves as the fallback image for artists without a dedicated photo.

Example: `input/images/artists/d4f7b9a1-1234-5678-abcd-ef0123456789`

### Physical release images

**Directory:** `input/images/physical/`
**No extension**
**No CLI equivalent** (manual only)

Photos of physical media (vinyl sleeves, CD cases) named by release UUID. These are copied to the output directory and can be referenced in the physical release HTML content.

Example: `input/images/physical/3ba21ea2-3ff4-41b6-991e-6bd4d26ab223`

## CLI vs. manual editing

The data files (rewrites, embeds, notes, ordering, ignore) are only read during `mblabelsite migrate`, which imports them into the SQLite database. After that, the database is the source of truth and the CLI commands are the preferred way to make changes.

The flat files in `input/` are useful for:

- Bulk editing (e.g., preparing rewrites for many releases at once before running `migrate`)
- Version control (the files can be committed to git)
- Rebuilding the database from scratch (run `migrate` to re-import everything)

Image files and static assets (CSS, favicon, header) have no CLI equivalent and must be managed manually in `input/`. They are copied to the output directory on every `generate` run.

After editing data files by hand, run `mblabelsite migrate` to import the changes into the database, then `mblabelsite generate` to rebuild the site.

After using CLI commands, just run `mblabelsite generate` (or one of the fetch commands, which regenerate automatically).
