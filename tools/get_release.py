import argparse
import logging
import pooch
import re
import requests
import shutil
import sys
import zipfile
from packaging.version import Version, InvalidVersion
from pathlib import Path



cache_dir: Path = Path.home() / ".cache" / "eng209" / "pooch"


def get_release_assets(repo: str, per_page: int = 100) -> list[dict]:
    """Fetch all releases from a GitHub repo, with pagination."""
    releases = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/releases"
        params = {"page": page, "per_page": per_page}
        response = requests.get(url, params=params)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        releases.extend(batch)
        page += 1
    return releases


def parse_tag(tag: str) -> tuple[(str | None, ...)]:
    match = re.match(r"^(v\d+(?:\.\d+){0,2})(?:-(.+))?$", tag)
    if match:
        return match.groups()
    return None, None


def select_latest_matching_release(
    releases: list[dict],
    version_prefix: str | None = None,
    label_regex: str | None = None,
) -> dict | None:
    matches = []
    for release in releases:
        version_tag, label = parse_tag(release["tag_name"])
        if not version_tag:
            continue
        if version_prefix and not version_tag.startswith(version_prefix):
            continue
        if label_regex and (label is None or not re.match(label_regex, label)):
            continue
        try:
            version_obj = Version(version_tag[1:])  # remove leading 'v'
        except InvalidVersion:
            continue
        matches.append((version_obj, release))
    if not matches:
        return None
    return max(matches, key=lambda x: x[0])[1]


def fetch_asset_with_pooch(
    asset_url: str, filename: str, known_hash: str | None = None
) -> str:
    """Download and cache the asset under .cache in script's folder"""
    script_dir = Path(__file__).parent.resolve()
    unpack = pooch.Unzip(extract_dir=script_dir.parent.resolve())
    return pooch.retrieve(
        url=asset_url,
        known_hash=known_hash,  # Skip integrity check
        fname=filename,
        path=cache_dir,
        processor=unpack,
        progressbar=True,
    )


def clean_cache():
    try:
        if cache_dir.exists() and cache_dir.is_dir():
            shutil.rmtree(cache_dir)
    except Exception as e:
        logger.warning(f"❌ Cannot clean cache {cache_dir}: {e}")
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version", metavar="V", help="Filter by minimum release version"
    )
    parser.add_argument("--label", metavar="R", help="Filter by release label (regex)")
    parser.add_argument(
        "--origin",
        metavar="Q",
        help="Set github source project URL",
        default="eng209/assets",
    )
    parser.add_argument("--clean", action="store_true", help="Erase download cache")
    parser.add_argument("--force", action="store_true", help="Bypass download cache")
    parser.add_argument("--verbose", action="store_true", help="Verbose")
    args = parser.parse_args()

    logger = pooch.get_logger()
    logger.setLevel(logging.ERROR)

    if args.verbose:
        logger.setLevel(logging.INFO)

    if args.clean:
        clean_cache()
        sys.exit(0)

    if args.force:
        clean_cache()

    releases = get_release_assets(args.origin)
    release = select_latest_matching_release(releases, args.version, args.label)

    if not release:
        logger.error("❌ No matching release found.")
    else:
        logger.info(f"📦 Selected release: {release['tag_name']}")
        for asset in release["assets"]:
            logger.info(f"⬇️  Downloading asset: {asset['name']}")
            local_path = fetch_asset_with_pooch(
                asset["browser_download_url"], asset["name"]
            )
            # logger.info(f"✅ Cached to: {local_path}")

