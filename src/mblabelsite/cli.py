"""Click CLI for mblabelsite."""

import logging
from pathlib import Path

import click

from mblabelsite.config import LABEL_ID
from mblabelsite.database import Database
from mblabelsite.fetcher import FetchError
from mblabelsite.fetcher import refresh as do_refresh
from mblabelsite.fetcher import total_refresh as do_total_refresh
from mblabelsite.fetcher import update as do_update
from mblabelsite.generator import generate_all


def _setup_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@click.group()
@click.option("--label", default=LABEL_ID, help="MusicBrainz label ID")
@click.option("--data-dir", default="data", type=click.Path(), help="Data directory")
@click.option("--input-dir", default="input", type=click.Path(), help="Input files directory")
@click.option("--output-dir", default="output", type=click.Path(), help="Output directory")
@click.option("--template-dir", default="templates", type=click.Path(), help="Templates directory")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.pass_context
def cli(ctx, label, data_dir, input_dir, output_dir, template_dir, debug):
    """Static site generator for tici taci records."""
    _setup_logging(debug)
    ctx.ensure_object(dict)
    ctx.obj["label"] = label
    ctx.obj["data_dir"] = Path(data_dir)
    ctx.obj["input_dir"] = Path(input_dir)
    ctx.obj["output_dir"] = Path(output_dir)
    ctx.obj["template_dir"] = Path(template_dir)
    ctx.obj["db_path"] = Path(data_dir) / "cache.db"


def _get_db(ctx) -> Database:
    return Database(ctx.obj["db_path"])


# --- Generation Commands ---


@cli.command()
@click.pass_context
def update(ctx):
    """Incremental update: fetch only new releases."""
    db = _get_db(ctx)
    try:
        do_update(db, ctx.obj["label"], ctx.obj["data_dir"], ctx.obj["output_dir"], ctx.obj["input_dir"])
        generate_all(db, ctx.obj["template_dir"], ctx.obj["input_dir"], ctx.obj["data_dir"], ctx.obj["output_dir"])
        click.echo("Update complete.")
    except FetchError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    finally:
        db.close()


@cli.command("refresh")
@click.option("--resume", "resume_after", default=None, help="Resume after this release ID (from a prior failed run)")
@click.pass_context
def refresh_cmd(ctx, resume_after):
    """Re-fetch all metadata, keep existing cover art."""
    db = _get_db(ctx)
    try:
        do_refresh(db, ctx.obj["label"], ctx.obj["data_dir"], ctx.obj["input_dir"], resume_after=resume_after)
        generate_all(db, ctx.obj["template_dir"], ctx.obj["input_dir"], ctx.obj["data_dir"], ctx.obj["output_dir"])
        click.echo("Refresh complete.")
    except FetchError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    finally:
        db.close()


@cli.command("total-refresh")
@click.option("--resume", "resume_after", default=None, help="Resume after this release ID (from a prior failed run)")
@click.pass_context
def total_refresh_cmd(ctx, resume_after):
    """Re-fetch everything including cover art."""
    db = _get_db(ctx)
    try:
        do_total_refresh(db, ctx.obj["label"], ctx.obj["data_dir"], ctx.obj["input_dir"], resume_after=resume_after)
        generate_all(db, ctx.obj["template_dir"], ctx.obj["input_dir"], ctx.obj["data_dir"], ctx.obj["output_dir"])
        click.echo("Total refresh complete.")
    except FetchError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    finally:
        db.close()


@cli.command()
@click.pass_context
def generate(ctx):
    """Generate HTML from cache without fetching."""
    db = _get_db(ctx)
    try:
        generate_all(db, ctx.obj["template_dir"], ctx.obj["input_dir"], ctx.obj["data_dir"], ctx.obj["output_dir"])
        click.echo("Generation complete.")
    finally:
        db.close()


@cli.command()
@click.pass_context
def migrate(ctx):
    """Migrate flat-file cache to SQLite (one-time)."""
    from mblabelsite.migrate import migrate_all

    db = _get_db(ctx)
    try:
        migrate_all(db, ctx.obj["data_dir"], ctx.obj["input_dir"])
        click.echo("Migration complete.")
    finally:
        db.close()


# --- Query Commands ---


@cli.command("list-releases")
@click.pass_context
def list_releases(ctx):
    """List all releases."""
    db = _get_db(ctx)
    try:
        releases = db.get_all_releases()
        for r in releases:
            ignored = " [IGNORED]" if db.is_ignored_release(r.id) else ""
            click.echo(f"{r.date[:4]} | {r.artist_credit} - {r.title} [{r.catno}]{ignored}")
    finally:
        db.close()


@cli.command("show-release")
@click.argument("release_name")
@click.pass_context
def show_release(ctx, release_name):
    """Show full details for a release (fuzzy search by name)."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        click.echo(f"ID:      {release.id}")
        click.echo(f"Artist:  {release.artist_credit}")
        click.echo(f"Title:   {release.title}")
        click.echo(f"Date:    {release.date}")
        click.echo(f"Label:   {release.label}")
        click.echo(f"Cat#:    {release.catno}")
        click.echo(f"Slug:    {release.slug}")
        click.echo(f"Artists: {', '.join(release.artist_ids)}")
        click.echo(f"Remixers: {', '.join(release.remixer_ids)}")
        click.echo(f"Mastering: {', '.join(release.mastering_ids)}")
        click.echo(f"Tracks:  {len(release.tracks)}")
        for t in release.tracks:
            ms = t.length_ms
            mins = int((ms / (1000 * 60)) % 60)
            secs = int((ms / 1000) % 60)
            click.echo(f"  {t.position}. {t.title} ({mins}:{secs:02d})")
    finally:
        db.close()


@cli.command()
@click.argument("query")
@click.pass_context
def search(ctx, query):
    """Search releases by title."""
    db = _get_db(ctx)
    try:
        results = db.search_releases_by_title(query)
        if not results:
            click.echo("No results found.")
            return
        for r in results:
            click.echo(f"{r.date[:4]} | {r.artist_credit} - {r.title} [{r.catno}]")
    finally:
        db.close()


# --- Data Manipulation Commands ---


@cli.command("add-bandcamp")
@click.argument("embed_code")
@click.argument("release_name")
@click.pass_context
def add_bandcamp(ctx, embed_code, release_name):
    """Add Bandcamp embed to a release."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.set_bandcamp_embed(release.id, embed_code)
        click.echo(f"Bandcamp embed set for: {release.title}")
    finally:
        db.close()


@cli.command("remove-bandcamp")
@click.argument("release_name")
@click.pass_context
def remove_bandcamp(ctx, release_name):
    """Remove Bandcamp embed from a release."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.remove_bandcamp_embed(release.id)
        click.echo(f"Bandcamp embed removed for: {release.title}")
    finally:
        db.close()


@cli.command("add-soundcloud")
@click.argument("url")
@click.argument("release_name")
@click.pass_context
def add_soundcloud(ctx, url, release_name):
    """Add SoundCloud embed to a release."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.set_soundcloud_embed(release.id, url)
        click.echo(f"SoundCloud embed set for: {release.title}")
    finally:
        db.close()


@cli.command("remove-soundcloud")
@click.argument("release_name")
@click.pass_context
def remove_soundcloud(ctx, release_name):
    """Remove SoundCloud embed from a release."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.remove_soundcloud_embed(release.id)
        click.echo(f"SoundCloud embed removed for: {release.title}")
    finally:
        db.close()


@cli.command("add-note")
@click.argument("release_name")
@click.argument("note")
@click.pass_context
def add_note(ctx, release_name, note):
    """Add/update release notes."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.set_release_note(release.id, note)
        click.echo(f"Note set for: {release.title}")
    finally:
        db.close()


@cli.command("remove-note")
@click.argument("release_name")
@click.pass_context
def remove_note(ctx, release_name):
    """Remove release notes."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.remove_release_note(release.id)
        click.echo(f"Note removed for: {release.title}")
    finally:
        db.close()


@cli.command("set-rewrite")
@click.argument("release_name")
@click.argument("slug")
@click.pass_context
def set_rewrite(ctx, release_name, slug):
    """Set URL slug for a release."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.set_release_rewrite(release.id, slug)
        click.echo(f"Rewrite set for: {release.title} -> {slug}")
    finally:
        db.close()


@cli.command("remove-rewrite")
@click.argument("release_name")
@click.pass_context
def remove_rewrite(ctx, release_name):
    """Remove URL slug override for a release."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.remove_release_rewrite(release.id)
        click.echo(f"Rewrite removed for: {release.title}")
    finally:
        db.close()


@cli.command("set-artist-rewrite")
@click.argument("artist_name")
@click.argument("slug")
@click.pass_context
def set_artist_rewrite(ctx, artist_name, slug):
    """Set URL slug for an artist."""
    db = _get_db(ctx)
    try:
        artist = _find_artist(db, artist_name)
        if not artist:
            return
        db.set_artist_rewrite(artist.id, slug)
        click.echo(f"Rewrite set for: {artist.name} -> {slug}")
    finally:
        db.close()


@cli.command("remove-artist-rewrite")
@click.argument("artist_name")
@click.pass_context
def remove_artist_rewrite(ctx, artist_name):
    """Remove artist slug override."""
    db = _get_db(ctx)
    try:
        artist = _find_artist(db, artist_name)
        if not artist:
            return
        db.remove_artist_rewrite(artist.id)
        click.echo(f"Rewrite removed for: {artist.name}")
    finally:
        db.close()


@cli.command("ignore-release")
@click.argument("release_name")
@click.pass_context
def ignore_release(ctx, release_name):
    """Mark a release as ignored."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.set_ignored_release(release.id)
        click.echo(f"Ignoring: {release.title}")
    finally:
        db.close()


@cli.command("unignore-release")
@click.argument("release_name")
@click.pass_context
def unignore_release(ctx, release_name):
    """Unmark a release as ignored."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.remove_ignored_release(release.id)
        click.echo(f"Unignored: {release.title}")
    finally:
        db.close()


@cli.command("set-physical")
@click.argument("release_name")
@click.argument("content")
@click.pass_context
def set_physical(ctx, release_name, content):
    """Set physical release info."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.set_physical_release(release.id, content)
        click.echo(f"Physical info set for: {release.title}")
    finally:
        db.close()


@cli.command("remove-physical")
@click.argument("release_name")
@click.pass_context
def remove_physical(ctx, release_name):
    """Remove physical release info."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        db.remove_physical_release(release.id)
        click.echo(f"Physical info removed for: {release.title}")
    finally:
        db.close()


@cli.command("set-artist-order")
@click.argument("release_name")
@click.argument("ids")
@click.pass_context
def set_artist_order(ctx, release_name, ids):
    """Set artist display ordering (comma-separated IDs)."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        id_list = [i.strip() for i in ids.split(",")]
        db.set_artist_ordering(release.id, id_list)
        click.echo(f"Artist ordering set for: {release.title}")
    finally:
        db.close()


@cli.command("set-mastering-order")
@click.argument("release_name")
@click.argument("ids")
@click.pass_context
def set_mastering_order(ctx, release_name, ids):
    """Set mastering display ordering (comma-separated IDs)."""
    db = _get_db(ctx)
    try:
        release = _find_release(db, release_name)
        if not release:
            return
        id_list = [i.strip() for i in ids.split(",")]
        db.set_mastering_ordering(release.id, id_list)
        click.echo(f"Mastering ordering set for: {release.title}")
    finally:
        db.close()


@cli.command("list-artists")
@click.pass_context
def list_artists(ctx):
    """List all artists."""
    db = _get_db(ctx)
    try:
        artists = db.get_all_artists()
        for a in artists:
            click.echo(f"{a.name} ({a.slug})")
    finally:
        db.close()


@cli.command("show-artist")
@click.argument("name")
@click.pass_context
def show_artist(ctx, name):
    """Show artist details."""
    db = _get_db(ctx)
    try:
        artist = _find_artist(db, name)
        if not artist:
            return
        click.echo(f"ID:   {artist.id}")
        click.echo(f"Name: {artist.name}")
        click.echo(f"Slug: {artist.slug}")

        for role, label in [("artist", "Releases"), ("remixer", "Remixes"), ("mastering", "Mastering")]:
            releases = db.get_releases_for_artist(artist.id, role)
            if releases:
                click.echo(f"\n{label}:")
                for r in releases:
                    click.echo(f"  {r.date[:4]} | {r.title} [{r.catno}]")
    finally:
        db.close()


# --- Helpers ---


def _find_release(db: Database, query: str):
    """Find a release by fuzzy title search. Returns the release or None."""
    results = db.search_releases_by_title(query)
    if not results:
        # Try by ID
        release = db.get_release(query)
        if release:
            return release
        click.echo(f"No release found matching: {query}")
        return None
    if len(results) == 1:
        return results[0]
    # Multiple matches — let user choose
    click.echo("Multiple matches found:")
    for i, r in enumerate(results):
        click.echo(f"  {i + 1}. {r.artist_credit} - {r.title} [{r.catno}]")
    choice = click.prompt("Select number", type=int)
    if 1 <= choice <= len(results):
        return results[choice - 1]
    click.echo("Invalid choice.")
    return None


def _find_artist(db: Database, query: str):
    """Find an artist by name search. Returns the artist or None."""
    artists = db.get_all_artists()
    query_lower = query.lower()
    matches = [a for a in artists if query_lower in a.name.lower()]
    if not matches:
        # Try by ID
        artist = db.get_artist(query)
        if artist:
            return artist
        click.echo(f"No artist found matching: {query}")
        return None
    if len(matches) == 1:
        return matches[0]
    click.echo("Multiple matches found:")
    for i, a in enumerate(matches):
        click.echo(f"  {i + 1}. {a.name}")
    choice = click.prompt("Select number", type=int)
    if 1 <= choice <= len(matches):
        return matches[choice - 1]
    click.echo("Invalid choice.")
    return None
