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

script_dir = Path(__file__).parent.resolve()
cache_dir = Path.home() / ".cache" / "eng209" / "pooch"


def get_release_assets(repo: str, per_page: int = 100) -> list:
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


def parse_tag(tag: str):
    match = re.match(r"^(v\d+(?:\.\d+){0,2})(?:-(.+))?$", tag)
    if match:
        return match.groups()
    return None, None


def select_latest_matching_release(releases: list, version_prefix=None, label_regex=None):
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


def clean_cache():
    try:
        if cache_dir.exists() and cache_dir.is_dir():
            shutil.rmtree(cache_dir)
    except Exception as e:
        logger.warning(f"❌ Cannot clean cache {cache_dir}: {e}")
        pass


def fetch_asset_with_pooch(asset_url: str, filename: str) -> str:
    """Download and cache the asset under .cache in script's folder"""
    unpack = pooch.Unzip(extract_dir=script_dir.parent.resolve())
    return pooch.retrieve(
        url=asset_url,
        known_hash=None, # Skip integrity check
        fname=filename,
        path= cache_dir,
        processor = unpack,
        progressbar=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", metavar="V", help="minimum release version prefix")
    parser.add_argument("--label", metavar="R", help="Release label (regex)")
    parser.add_argument("--origin", metavar="Q", help="Github project", default="eng209/assets")
    parser.add_argument("--clean", action="store_true", help="Delete cache")
    parser.add_argument("--force", action="store_true", help="Delete cache")

    args = parser.parse_args()

    logger = pooch.get_logger()
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
            local_path = fetch_asset_with_pooch(asset["browser_download_url"], asset["name"])
            # logger.info(f"✅ Cached to: {local_path}")

