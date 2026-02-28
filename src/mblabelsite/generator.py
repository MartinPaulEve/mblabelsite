"""HTML generation from database and templates."""

import logging
import re
import shutil
from pathlib import Path

from PIL import Image

from mblabelsite.database import Database
from mblabelsite.models import Artist, Release
from mblabelsite.templates import load_release_template, load_template

logger = logging.getLogger(__name__)


def generate_release_page(
    release: Release,
    db: Database,
    template_dir: Path,
    input_dir: Path,
    data_dir: Path,
    output_dir: Path,
) -> bool:
    """Generate HTML page for a single release."""
    template_html = load_release_template(str(template_dir), release.id)
    if template_html is None:
        logger.error("Cannot load release template for %s", release.id)
        return False

    # Basic replacements
    template_html = template_html.replace("[ARTIST]", release.artist_credit)
    template_html = template_html.replace("[TITLE]", release.title)
    template_html = template_html.replace("[YEAR]", release.date[:4] if release.date else "")
    template_html = template_html.replace("[CATNO]", release.catno)
    template_html = template_html.replace(
        "[COVERIMAGE]", f"../images/covers/{release.id}"
    )
    template_html = template_html.replace("[RELEASEID]", release.id)

    # Artist links
    template_html = _replace_artists(
        template_html, release, db, template_dir
    )

    # Remixer links
    template_html = _replace_remixers(template_html, release, db, template_dir)

    # Mastering links
    template_html = _replace_mastering(template_html, release, db, template_dir)

    # Cover art designer links
    template_html = _replace_cover_art_designers(
        template_html, release, db, template_dir
    )

    # Purchase links
    template_html = _replace_purchases(template_html, release, db, template_dir)

    # Track list
    template_html = _replace_tracks(template_html, release, template_dir)

    # SoundCloud
    template_html = _replace_soundcloud(template_html, release, db, template_dir)

    # Bandcamp
    template_html = _replace_bandcamp(template_html, release, db, template_dir)

    # Physical
    template_html = _replace_physical(template_html, release, db, template_dir, input_dir, output_dir)

    # Notes
    template_html = _replace_notes(template_html, release, db, template_dir)

    # Image dimensions (read from data_dir where covers are stored)
    cover_path = data_dir / "covers" / release.id
    if cover_path.exists():
        try:
            image = Image.open(cover_path)
            width, height = image.size
            template_html = template_html.replace("[[IMAGEHEIGHT]]", str(height))
            template_html = template_html.replace("[[IMAGEWIDTH]]", str(width))
        except Exception:
            template_html = template_html.replace("[[IMAGEHEIGHT]]", "0")
            template_html = template_html.replace("[[IMAGEWIDTH]]", "0")
    else:
        template_html = template_html.replace("[[IMAGEHEIGHT]]", "0")
        template_html = template_html.replace("[[IMAGEWIDTH]]", "0")

    # Write output files
    releases_dir = output_dir / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)

    # Write UUID-named file
    (releases_dir / f"{release.id}.html").write_text(template_html)

    # Write slug-named file
    slug = _get_effective_slug(release, db)
    if slug and slug != release.id:
        (releases_dir / f"{slug}.html").write_text(template_html)

    return True


def _remove_placeholder_line(html: str, placeholder: str) -> str:
    """Remove an entire line containing a placeholder to avoid blank lines."""
    return re.sub(r'\n[ \t]*' + re.escape(placeholder), '', html)


def _get_effective_slug(release: Release, db: Database) -> str:
    """Get the effective slug for a release, checking rewrites first."""
    rewrite = db.get_release_rewrite(release.id)
    if rewrite:
        return rewrite
    return release.slug


def _get_effective_artist_slug(artist: Artist, db: Database) -> str:
    """Get the effective slug for an artist, checking rewrites first."""
    rewrite = db.get_artist_rewrite(artist.id)
    if rewrite:
        return rewrite
    return artist.slug


def _replace_artists(
    template_html: str, release: Release, db: Database, template_dir: Path
) -> str:
    """Generate artist links and replace [ARTISTS] placeholder."""
    artist_template = load_template(str(template_dir), "template_artists")
    if not artist_template:
        return template_html.replace("[ARTISTS]", "")

    # Get priority artist ordering
    priority_ids = db.get_artist_ordering(release.id)

    artist_list = []
    primary_artist = None

    for aid in release.artist_ids:
        aid = aid.strip()
        if aid in priority_ids:
            continue
        artist = db.get_artist(aid)
        if artist is None:
            continue

        if artist.name == release.artist_credit:
            primary_artist = artist
        else:
            artist_list.append(artist)

    # Sort non-primary by name
    artist_list.sort(key=lambda a: a.name)

    # Insert primary at front
    if primary_artist:
        artist_list.insert(0, primary_artist)

    # Prepend priority artists (in reverse so first priority ends up first)
    for aid in reversed(priority_ids):
        aid = aid.strip()
        if aid:
            artist = db.get_artist(aid)
            if artist:
                artist_list.insert(0, artist)

    # Build HTML
    artists_html = ""
    for artist in artist_list:
        slug = _get_effective_artist_slug(artist, db)
        link = f'<a href="../artists/{slug}.html">{artist.name}</a>\n'
        artists_html += artist_template.replace("[ARTIST]", link)

    return template_html.replace("[ARTISTS]", artists_html)


def _replace_remixers(
    template_html: str, release: Release, db: Database, template_dir: Path
) -> str:
    """Generate remixer links and replace [REMIXERS] placeholder."""
    if not release.remixer_ids:
        return template_html.replace("[REMIXERS]", "")

    remixer_list = []
    for rid in release.remixer_ids:
        rid = rid.strip()
        artist = db.get_artist(rid)
        if artist:
            remixer_list.append(artist)

    remixer_list.sort(key=lambda a: a.name)

    if not remixer_list:
        return template_html.replace("[REMIXERS]", "")

    remixers_html = '<li>&nbsp;</li><li class="artists_remix"><strong class="artists_label">Remixed by:</strong></li>'
    artist_template = load_template(str(template_dir), "template_artists")
    for artist in remixer_list:
        slug = _get_effective_artist_slug(artist, db)
        link = f'<a href="../artists/{slug}.html">{artist.name}</a>\n'
        remixers_html += artist_template.replace("[ARTIST]", link)

    return template_html.replace("[REMIXERS]", remixers_html)


def _replace_mastering(
    template_html: str, release: Release, db: Database, template_dir: Path
) -> str:
    """Generate mastering links and replace [MASTERING] placeholder."""
    if not release.mastering_ids:
        return template_html.replace("[MASTERING]", "")

    priority_ids = db.get_mastering_ordering(release.id)

    mastering_list = []
    for mid in release.mastering_ids:
        mid = mid.strip()
        if mid in priority_ids:
            continue
        artist = db.get_artist(mid)
        if artist:
            mastering_list.append(artist)

    mastering_list.sort(key=lambda a: a.name)

    # Prepend priority mastering engineers
    for mid in reversed(priority_ids):
        mid = mid.strip()
        if mid:
            artist = db.get_artist(mid)
            if artist:
                mastering_list.insert(0, artist)

    if not mastering_list:
        return template_html.replace("[MASTERING]", "")

    mastering_html = '<li>&nbsp;</li><li class="artists_remix"><strong class="artists_label">Mastered by:</strong></li>'
    artist_template = load_template(str(template_dir), "template_artists")
    for artist in mastering_list:
        slug = _get_effective_artist_slug(artist, db)
        link = f'<a href="../artists/{slug}.html">{artist.name}</a>\n'
        mastering_html += artist_template.replace("[ARTIST]", link)

    return template_html.replace("[MASTERING]", mastering_html)


def _replace_cover_art_designers(
    template_html: str, release: Release, db: Database, template_dir: Path
) -> str:
    """Generate cover art designer links and replace [COVERARTDESIGNER] placeholder."""
    if "[COVERARTDESIGNER]" not in template_html:
        return template_html

    if not release.cover_art_designer_ids:
        return _remove_placeholder_line(template_html, "[COVERARTDESIGNER]")

    designer_list = []
    for did in release.cover_art_designer_ids:
        artist = db.get_artist(did)
        if artist:
            designer_list.append(artist)

    if not designer_list:
        return _remove_placeholder_line(template_html, "[COVERARTDESIGNER]")

    designer_html = '<li>&nbsp;</li><li class="artists_remix"><strong class="artists_label">Cover art by:</strong></li>'
    artist_template = load_template(str(template_dir), "template_artists")
    for artist in designer_list:
        slug = _get_effective_artist_slug(artist, db)
        link = f'<a href="../artists/{slug}.html">{artist.name}</a>\n'
        designer_html += artist_template.replace("[ARTIST]", link)

    return template_html.replace("[COVERARTDESIGNER]", designer_html)


def _replace_purchases(
    template_html: str, release: Release, db: Database, template_dir: Path
) -> str:
    """Generate purchase links and replace [PURCHASEINFO] placeholder."""
    if not release.purchase_links:
        return template_html.replace("[PURCHASEINFO]", "")

    purchases_html = ""
    for i, link in enumerate(release.purchase_links):
        if i == 0:
            purchases_html += f'<a href="{link.url}">{link.store_name}</a>'
        else:
            purchases_html += f' / <a href="{link.url}">{link.store_name}</a>'

    purchase_template = load_template(str(template_dir), "template_purchase")
    if purchase_template:
        purchase = purchase_template.replace("[PURCHASELINKS]", purchases_html)
    else:
        purchase = ""

    return template_html.replace("[PURCHASEINFO]", purchase)


def _replace_tracks(template_html: str, release: Release, template_dir: Path) -> str:
    """Generate track list and replace [TRACKS] placeholder."""
    if not release.tracks:
        return template_html.replace("[TRACKS]", "")

    track_list_html = ""
    for track in release.tracks:
        ms = track.length_ms
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        track_list_html += f"<li>{track.title} ({minutes}:{seconds:02d})</li>"

    tracks_template = load_template(str(template_dir), "template_tracks")
    if tracks_template:
        tracks_html = tracks_template.replace("[TRACKS]", track_list_html)
    else:
        tracks_html = ""

    return template_html.replace("[TRACKS]", tracks_html)


def _replace_soundcloud(
    template_html: str, release: Release, db: Database, template_dir: Path
) -> str:
    """Replace [SOUNDCLOUD] placeholder with embed if available."""
    soundcloud_url = db.get_soundcloud_embed(release.id)
    if not soundcloud_url:
        return template_html.replace("[SOUNDCLOUD]", "")

    sc_template = load_template(str(template_dir), "template_soundcloud")
    if sc_template:
        soundcloud_html = sc_template.replace("[EMBEDURL]", soundcloud_url)
    else:
        soundcloud_html = ""

    return template_html.replace("[SOUNDCLOUD]", soundcloud_html)


def _replace_bandcamp(
    template_html: str, release: Release, db: Database, template_dir: Path
) -> str:
    """Replace [BANDCAMP] placeholder with embed if available."""
    bandcamp_code = db.get_bandcamp_embed(release.id)
    if not bandcamp_code:
        return template_html.replace("[BANDCAMP]", "")

    bc_template = load_template(str(template_dir), "template_bandcamp")
    if bc_template:
        bandcamp_html = bc_template.replace("[EMBEDURL]", bandcamp_code)
    else:
        bandcamp_html = ""

    return template_html.replace("[BANDCAMP]", bandcamp_html)


def _replace_physical(
    template_html: str,
    release: Release,
    db: Database,
    template_dir: Path,
    input_dir: Path,
    output_dir: Path,
) -> str:
    """Replace [PHYSICAL] placeholder with physical release info."""
    physical_content = db.get_physical_release(release.id)

    # Copy physical image if it exists
    src_img = input_dir / "images" / "physical" / release.id
    if src_img.exists():
        dst_dir = output_dir / "images" / "physical"
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(src_img), str(dst_dir / release.id))

    if not physical_content:
        return template_html.replace("[PHYSICAL]", "")

    phys_template = load_template(str(template_dir), "template_physical")
    if phys_template:
        physical_html = phys_template.replace("[[PHYSICAL]]", physical_content)
    else:
        physical_html = ""

    return template_html.replace("[PHYSICAL]", physical_html)


def _replace_notes(
    template_html: str, release: Release, db: Database, template_dir: Path
) -> str:
    """Replace [NOTES] placeholder with release notes."""
    notes = db.get_release_note(release.id)
    if not notes:
        return template_html.replace("[NOTES]", "")

    notes_template = load_template(str(template_dir), "template_notes")
    if notes_template:
        notes_html = notes_template.replace("[[NOTES]]", notes)
    else:
        notes_html = ""

    return template_html.replace("[NOTES]", notes_html)


def generate_artist_page(
    artist_id: str,
    db: Database,
    template_dir: Path,
    input_dir: Path,
    output_dir: Path,
) -> bool:
    """Generate HTML page for a single artist."""
    artist = db.get_artist(artist_id)
    if artist is None:
        logger.error("Artist not found: %s", artist_id)
        return False

    # Load template
    artist_template = load_template(str(template_dir), "artist")
    if artist_template is None:
        return False

    artist_template = artist_template.replace("[ARTIST]", artist.name)
    artist_template = artist_template.replace("[ARTISTID]", artist_id)

    # Releases section
    artist_template = _build_artist_release_section(
        artist_template, "[[RELEASES]]", "artist_releases",
        artist_id, "artist", db, template_dir, input_dir
    )

    # Remixes section
    artist_template = _build_artist_release_section(
        artist_template, "[[REMIXES]]", "artist_remixes",
        artist_id, "remixer", db, template_dir, input_dir
    )

    # Masters section
    artist_template = _build_artist_release_section(
        artist_template, "[[MASTERS]]", "artist_masters",
        artist_id, "mastering", db, template_dir, input_dir
    )

    # Copy artist image
    src_img = input_dir / "images" / "artists" / artist_id
    dst_dir = output_dir / "images" / "artists"
    dst_dir.mkdir(parents=True, exist_ok=True)

    if src_img.exists():
        shutil.copyfile(str(src_img), str(dst_dir / artist_id))
    else:
        generic = input_dir / "images" / "artists" / "generic"
        if generic.exists():
            shutil.copyfile(str(generic), str(dst_dir / artist_id))

    # Image dimensions
    img_path = dst_dir / artist_id
    if img_path.exists():
        try:
            image = Image.open(img_path)
            width, height = image.size
            artist_template = artist_template.replace("[[IMAGEHEIGHT]]", str(height))
            artist_template = artist_template.replace("[[IMAGEWIDTH]]", str(width))
        except Exception:
            artist_template = artist_template.replace("[[IMAGEHEIGHT]]", "0")
            artist_template = artist_template.replace("[[IMAGEWIDTH]]", "0")
    else:
        artist_template = artist_template.replace("[[IMAGEHEIGHT]]", "0")
        artist_template = artist_template.replace("[[IMAGEWIDTH]]", "0")

    # Write output files
    artists_dir = output_dir / "artists"
    artists_dir.mkdir(parents=True, exist_ok=True)

    # Always write UUID-named file
    (artists_dir / f"{artist_id}.html").write_text(artist_template)

    # Write slug-named file
    slug = _get_effective_artist_slug(artist, db)
    if slug and slug != artist_id:
        (artists_dir / f"{slug}.html").write_text(artist_template)

    return True


def _build_artist_release_section(
    template: str,
    placeholder: str,
    section_template_name: str,
    artist_id: str,
    role: str,
    db: Database,
    template_dir: Path,
    input_dir: Path,
) -> str:
    """Build a release list section (releases/remixes/mastering) for an artist page."""
    releases = db.get_releases_for_artist(artist_id, role)

    # Filter out ignored releases
    filtered = []
    for r in releases:
        if not db.is_ignored_release(r.id):
            filtered.append(r)

    if not filtered:
        return template.replace(placeholder, "")

    section_tpl = load_template(str(template_dir), section_template_name)
    if not section_tpl:
        return template.replace(placeholder, "")

    releases_html = ""
    for release in filtered:
        slug = _get_effective_slug(release, db)
        line = (
            f'<li><a href="../releases/{slug}.html">'
            f"{release.title} / {release.date[:4]} / {release.catno}</a></li>"
        )
        releases_html += line

    section_html = section_tpl.replace("[[RELEASES]]", releases_html)
    return template.replace(placeholder, section_html)


def generate_homepage(
    db: Database,
    template_dir: Path,
    output_dir: Path,
) -> bool:
    """Generate the homepage index.html."""
    master_template = load_template(str(template_dir), "template")
    if master_template is None:
        return False

    releases = db.get_all_releases()

    # Filter out ignored releases
    filtered = [r for r in releases if not db.is_ignored_release(r.id)]

    output_html = '<div id="coverart" class="box"><div class="table"><ul class="collage_images" id="collage_book">'

    for release in filtered:
        slug = _get_effective_slug(release, db)
        output_html += (
            f'<li class="image_group">'
            f'<a href="releases/{slug}.html">'
            f'<img class="tooltip_interactive" '
            f'src="images/covers/{release.id}" '
            f'alt="{release.artist_credit} - {release.title} [{release.date}] ({release.label})" '
            f'title="{release.artist_credit} - {release.title} [{release.date}] ({release.label})" '
            f'data-title-plain="{release.artist_credit} - {release.title} [{release.date}] ({release.label})" '
            f'width="118" /></a></li>'
        )

    output_html += "</ul></div></div>"

    master_template = master_template.replace("[CONTENTS]", output_html)

    (output_dir / "index.html").write_text(master_template)
    return True


def copy_static_assets(input_dir: Path, data_dir: Path, output_dir: Path):
    """Copy CSS, images, and cover art to the output directory."""
    # CSS
    css_dir = output_dir / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    for css_file in ["music.css", "release.css"]:
        src = input_dir / css_file
        if src.exists():
            shutil.copyfile(str(src), str(css_dir / css_file))

    # Site images
    site_dir = output_dir / "images" / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    for img_file in ["header.png", "favicon.png"]:
        src = input_dir / img_file
        if src.exists():
            shutil.copyfile(str(src), str(site_dir / img_file))

    # Cover art from data_dir
    covers_src = data_dir / "covers"
    if covers_src.is_dir():
        covers_dst = output_dir / "images" / "covers"
        covers_dst.mkdir(parents=True, exist_ok=True)
        for cover in covers_src.iterdir():
            if cover.is_file():
                shutil.copyfile(str(cover), str(covers_dst / cover.name))


def generate_all(
    db: Database,
    template_dir: Path,
    input_dir: Path,
    data_dir: Path,
    output_dir: Path,
):
    """Generate all HTML pages and copy static assets."""
    # Ensure output directories
    for subdir in ["releases", "artists", "images/covers", "images/artists",
                   "images/physical", "images/site", "css"]:
        (output_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Copy static assets (including covers from data_dir)
    copy_static_assets(input_dir, data_dir, output_dir)

    # Generate release pages
    releases = db.get_all_releases()
    for release in releases:
        if not db.is_ignored_release(release.id):
            generate_release_page(release, db, template_dir, input_dir, data_dir, output_dir)

    # Generate artist pages
    artists = db.get_all_artists()
    for artist in artists:
        generate_artist_page(artist.id, db, template_dir, input_dir, output_dir)

    # Generate homepage
    generate_homepage(db, template_dir, output_dir)
