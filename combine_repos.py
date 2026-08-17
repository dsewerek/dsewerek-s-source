"""
combine_repos.py

Combines multiple AltStore/SideStore/Feather-compatible source.json repos into
three output source files, deduping and grouping multi-version app entries.

Merge rule (same priority model as the original single-repo script):
  1. Whatever is already committed in the output file is the highest-priority
     "manual" layer. Its app metadata (name, icon, description, etc.) is never
     overwritten by scraped data.
  2. Source repos are processed in the order they're listed in CONFIG. The
     first repo (or local file) to introduce a bundle ID "owns" that app's
     metadata. Every repo processed after that, for the same bundle ID, only
     contributes new *versions* -- it can never replace existing metadata.
  3. Versions are deduped by (version, buildVersion) and sorted newest-first.
     Top-level version/size/downloadURL are synced to the newest version.

This one function is reused for all three outputs, so an app that appears
multiple times inside a single repo's own apps[] array (a common mess in
scraped/aggregator sources) gets grouped into one entry exactly the same way
duplicates across repos do.
"""

import os
import json
import copy
import requests

# --------------------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------------------

OUTPUT_DIR = "."  # where the 3 output json files get written

# --- 1. Selected apps: pick specific bundle IDs out of specific repos ---
# Same shape as your old script. Dict order = priority order for metadata.
SELECTED_APPS_CONFIG = {
    "https://raw.githubusercontent.com/titouan336/Spotify-AltStoreRepo-mirror/refs/heads/main/source.json": [
        "com.spotify.client",
        "com.spotify.client.patched",
    ]
    # "https://github.com/someone/another-repo/blob/main/source.json": [
    #     "com.example.app",
    # ],
}
SELECTED_OUTPUT_FILE = "selected.json"
SELECTED_BASE_META = {
    "name": "dsewerek's selected apps",
    "subtitle": "hand-picked apps, all versions kept",
    "description": "a curated pick of specific apps pulled from specific repos.",
    "iconURL": "https://i.imgur.com/KSSr4ML.png",
    "headerURL": "https://file.garden/aeuRASVxx2XDWdox/2026-04-24T18_29_07.png",
    "tintColor": "#155713",
    "featuredApps": [],
}

# --- 2. General apps: ingest every app from these full repos ---
GENERAL_REPOS = [
    "https://raw.githubusercontent.com/Nyasami/Ksign/refs/heads/main/repo.json",
    "https://alt.crystall1ne.dev",
    "https://repository.apptesters.org",
    "https://community-apps.sidestore.io/sidecommunity.json",
    "https://github.com/LiveContainer/LiveContainer/releases/download/1.0/apps.json",
    "https://buildbot.libretro.com/stable/altstore.json",
    "https://quarksources.github.io/quantumsource++.json",
    "https://alts.lao.sb",
    "https://azu0609.github.io/repo/altstore_repo.json",
    "https://raw.githubusercontent.com/Omni-Development/The-Omni-Repository/refs/heads/main/app-repo.json",
    "https://ftrepo.xyz/apps.json",
    "https://driftywinds.github.io/repos/esign.json",
    "https://qnblackcat.github.io/AltStore/apps.json",
    "https://spotc-repo.yodaluca.dev/AltStore%20Repo.json",
    "https://raw.githubusercontent.com/RealBlackAstronaut/CelestialRepo/main/CelestialRepo.json",
    "https://enmity-mod.github.io/repo/altstore.json",
    "https://apps.altstore.io",
    "https://randomblock1.com/altstore/apps.json",
    "https://website.burrito.software/altstore/channels/burritosource.json",
    "https://bit.ly/Altstore-complete",
    "https://raw.githubusercontent.com/paigely/Navic/refs/heads/master/app-repo.json",
    "https://quarksources.github.io/quantumsource.json",
    "https://wuxu1.github.io/wuxu-complete.json",
    "https://raw.githubusercontent.com/TheNightmanCodeth/chromium-ios/master/altstore-source.json",
    "https://bit.ly/wuxuslibraryplus",
    "https://stikdebug.xyz/index.json",
    "https://alt.getutm.app",
    "https://ish.app/altstore.json",
    "https://github.com/chachillie/Flycast-iOS/raw/main/flycast-ios.json",
    "https://raw.githubusercontent.com/lo-cafe/winston-altstore/main/apps.json",
    "https://raw.githubusercontent.com/Aidoku/Aidoku/altstore/apps.json",
    "https://web.archive.org/web/20250913142230id_/https://aio.zxcvbn.fyi/r/repo.feather.json",
    "https://raw.githubusercontent.com/jay-goobuh/samhub/main/apps",
    "https://flyinghead.github.io/flycast-builds/altstore.json",
    "https://raw.githubusercontent.com/Dan1elTheMan1el/IOS-Repo/refs/heads/main/altstore-repo.json",
    "https://raw.githubusercontent.com/Balackburn/YTLitePlusAltstore/main/apps.json",
    "https://github.com/khcrysalis/Feather/raw/main/app-repo.json",
    "https://alt.thatstel.la",
    "https://raw.githubusercontent.com/bunny-mod/BunnyTweak/refs/heads/main/app-repo.json",
    "https://raw.githubusercontent.com/arichornlover/arichornlover.github.io/main/apps2.json",
    "https://raw.githubusercontent.com/titouan336/Spotify-AltStoreRepo-mirror/refs/heads/main/source.json",
    "https://apps.sidestore.io",
    "https://raw.githubusercontent.com/arichornlover/arichornlover.github.io/main/apps.json",
    "https://raw.githubusercontent.com/actuallyaridan/NeoFreeBird/refs/heads/main/AltSource.json",
    "https://therealfoxster.github.io/altsource/apps.json",
    "https://driftywinds.github.io/AltStore/apps.json",
    "https://repo.madari.media/nightly/repo.json",
    "https://altstore.fouadraheb.com",
    "https://connect.sidestore.io/apps.json",
    "https://apps.manicemu.site/altstore",
    "https://raw.githubusercontent.com/swaggyP36000/TrollStore-IPAs/main/apps.json",
    "https://theodyssey.dev/altstore/odysseysource.json",
    "https://pokemmo.com/altstore/",
    "https://taurine.app/altstore/taurinestore.json",
    "https://appmarket.tech/altstore.json",
    "https://bit.ly/dvntm_esign",
    "https://raw.githubusercontent.com/vizunchik/AltStoreRus/master/apps.json",
    "https://altstore.ignitedemulator.com",
    "https://apps.nabzclan.vip/repos/altstore.php",
    "https://apps.nabzclan.vip/repos/esign.php",
    "https://bit.ly/40Isul6",
    "https://github.com/dvntm0/AltStore/raw/refs/heads/main/esign.json",
    "https://github.com/dvntm0/AltStore/raw/refs/heads/main/feather.json",
    "https://pokemmo.com/altstore",
    "https://pokemmo.eu/altstore",
    "https://provenance-emu.com/apps.json",
    "https://raw.githubusercontent.com/Neoncat-OG/TrollStore-IPAs/main/apps_esign.json",
    "https://raw.githubusercontent.com/WhySooooFurious/Ultimate-Sideloading-Guide/refs/heads/main/app-repo.json",
    "https://raw.githubusercontent.com/YourName028/System-Apps/main/repo.json",
    "https://raw.githubusercontent.com/driftywinds/driftywinds.github.io/master/AltStore/apps.json",
    "https://raw.githubusercontent.com/notrifty1/riftysrepo/refs/heads/main/reposource.json",
    "https://raw.githubusercontent.com/swaggyP36000/TrollStore-IPAs/main/apps_esign.json",
    "https://rickowens.su/repo.json",
    "https://wuxu1.github.io/wuxu-complete-plus.json",
    "https://xitrix.github.io/iTorrent/AltStore.json"
]
GENERAL_OUTPUT_FILE = "general.json"
GENERAL_BASE_META = {
    "name": "dsewerek's general apps",
    "subtitle": "everything from every selected repo, organized",
    "description": "all apps from the selected repos, deduped and grouped by version.",
    "iconURL": "https://i.imgur.com/KSSr4ML.png",
    "headerURL": "https://file.garden/aeuRASVxx2XDWdox/2026-04-24T18_29_07.png",
    "tintColor": "#155713",
    "featuredApps": [],
}

# --- 3. Fastsign: scraped live and run through the same organizing pass ---
FASTSIGN_SOURCE_URL = "https://fastsign.dev/repo.json"
FASTSIGN_OUTPUT_FILE = "fastsign.json"
FASTSIGN_BASE_META = {
    "name": "fastsign (organized)",
    "subtitle": "fastsign.dev's repo, deduped and grouped by version - by dsewerek",
    "description": "a re-organized mirror of fastsign.dev's live source. by dsewerek :p",
    "iconURL": "https://i.imgur.com/KSSr4ML.png",
    "headerURL": "https://file.garden/aeuRASVxx2XDWdox/2026-04-24T18_29_07.png",
    "tintColor": "#155713",
    "featuredApps": [],
}

REQUEST_TIMEOUT = 400

# --------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------


def get_raw_url(url):
    """Converts standard GitHub blob URLs to raw content URLs if needed."""
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url


def fetch_json(url):
    target = get_raw_url(url)
    try:
        resp = requests.get(target, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[-] Skipped source due to error: {target} -> {e}")
        return None


def load_output_file(path):
    """Loads a previously-committed output file, if it exists. This becomes
    the highest-priority ('manual') layer."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def version_key(v):
    return (v.get("version"), str(v.get("buildVersion")))


def get_incoming_versions(app):
    """Some source repos (e.g. apptesters.org-style aggregators) publish an
    empty `versions: []` and put the actual version info as flat top-level
    fields on the app instead. Without this, those apps get merged with zero
    versions and become uninstallable. If `versions` is empty/missing but the
    app has top-level version + downloadURL, synthesize a single version
    entry from them."""
    versions = app.get("versions") or []
    if versions:
        return versions

    if app.get("downloadURL") and app.get("version"):
        synthesized = {
            "version": app.get("version"),
            "date": app.get("versionDate") or app.get("date") or "",
            "downloadURL": app.get("downloadURL"),
            "size": app.get("size"),
            "localizedDescription": app.get("localizedDescription"),
            "minOSVersion": app.get("minOSVersion"),
            "maxOSVersion": app.get("maxOSVersion"),
        }
        # Drop empty/None fields so we don't pollute the output with nulls.
        return [{k: v for k, v in synthesized.items() if v not in (None, "")}]

    return []


FALLBACK_DATE = "2000-01-01"  # sorts to the bottom, never wins "latest"


def normalize_version(v):
    """AltStore's source schema treats `buildVersion` and `date` as required
    (non-optional) fields on every version entry. Its decoder fails the
    *entire* source file if even one version anywhere is missing a required
    field -- and most of the repos we scrape simply don't provide
    buildVersion, and a good chunk skip date too. Backfill both so the file
    always decodes, without touching entries that already have real data."""
    v = dict(v)  # don't mutate the source dict
    if not v.get("buildVersion"):
        v["buildVersion"] = v.get("version", "")
    if not v.get("date"):
        v["date"] = FALLBACK_DATE
    if v.get("size") is None:
        v["size"] = 0
    return v


def merge_versions(existing_versions, incoming_versions):
    """Adds any version from incoming_versions not already present. Existing
    versions are never overwritten (priority stays with whoever added them
    first)."""
    normalized_existing = [normalize_version(v) for v in existing_versions]
    existing_versions.clear()
    existing_versions.extend(normalized_existing)

    seen = {version_key(v) for v in existing_versions}
    added = 0
    for raw_v in incoming_versions:
        v = normalize_version(raw_v)
        k = version_key(v)
        if k not in seen:
            existing_versions.append(v)
            seen.add(k)
            added += 1
    existing_versions.sort(key=lambda x: x.get("date", ""), reverse=True)
    return added


def sync_top_level_fields(app):
    """Points the app's top-level version/size/downloadURL at the newest
    version entry, the way AltStore expects."""
    versions = app.get("versions", [])
    if not versions:
        return
    latest = versions[0]
    app["version"] = latest.get("version")
    app["versionDate"] = str(latest.get("date", "")).split("T")[0]
    app["size"] = latest.get("size")
    app["downloadURL"] = latest.get("downloadURL")


FALLBACK_ICON_URL = "https://i.imgur.com/KSSr4ML.png"


def merge_app_into_map(apps_map, app):
    """The core rule: first writer of a bundle ID owns its metadata forever
    (within this run); every later occurrence of that bundle ID only
    contributes new versions. This is what groups duplicate entries -- both
    within one repo's apps[] array and across repos -- into one entry."""
    bid = app.get("bundleIdentifier")
    if not bid:
        return

    incoming_versions = get_incoming_versions(app)

    if bid not in apps_map:
        # New app: take a deep copy so later mutations don't affect the
        # source data, then dedupe its own internal versions list.
        new_app = copy.deepcopy(app)
        if not new_app.get("name"):
            new_app["name"] = bid
        # Feather (and AltStore itself) treat iconURL as a REQUIRED,
        # non-optional field on every app. Some aggregator sources ship an
        # empty string here -- one single app with a missing/empty iconURL
        # crashes decoding of the *entire* apps array, not just that app.
        if not new_app.get("iconURL"):
            new_app["iconURL"] = new_app.get("icon") or FALLBACK_ICON_URL
        new_app["versions"] = []
        merge_versions(new_app["versions"], incoming_versions)
        sync_top_level_fields(new_app)
        apps_map[bid] = new_app
        print(f"[+] New app tracked: {bid}")
    else:
        existing = apps_map[bid]
        # Backfill on existing entries too, in case they were loaded from a
        # previously-committed output file that predates this check.
        if not existing.get("iconURL"):
            existing["iconURL"] = existing.get("icon") or FALLBACK_ICON_URL
        added = merge_versions(existing.setdefault("versions", []), incoming_versions)
        if added:
            sync_top_level_fields(existing)
            print(f"[*] Merged {added} new version(s) into existing app: {bid}")


def build_source(base_meta, existing_apps_map_seed, apps_map):
    """Assembles the final source.json structure."""
    out = dict(base_meta)
    out["apps"] = list(apps_map.values())
    return out


def write_json(path, data):
    full_path = os.path.join(OUTPUT_DIR, path)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[+] Wrote {full_path} ({len(data.get('apps', []))} apps)")


# --------------------------------------------------------------------------
# BUILDERS
# --------------------------------------------------------------------------


def build_selected():
    print("\n=== Building selected.json ===")
    existing = load_output_file(os.path.join(OUTPUT_DIR, SELECTED_OUTPUT_FILE))
    apps_map = {}

    # Local/manual layer goes first so it always owns its own apps' metadata.
    if existing:
        for app in existing.get("apps", []):
            merge_app_into_map(apps_map, app)
        base_meta = {k: existing.get(k, v) for k, v in SELECTED_BASE_META.items()}
    else:
        base_meta = SELECTED_BASE_META

    for repo_url, bundle_ids in SELECTED_APPS_CONFIG.items():
        print(f"[*] Scraping (selected): {repo_url}")
        data = fetch_json(repo_url)
        if not data:
            continue
        wanted = set(bundle_ids)
        for app in data.get("apps", []):
            if app.get("bundleIdentifier") in wanted:
                merge_app_into_map(apps_map, app)

    write_json(SELECTED_OUTPUT_FILE, build_source(base_meta, existing, apps_map))


def build_general():
    print("\n=== Building general.json ===")
    existing = load_output_file(os.path.join(OUTPUT_DIR, GENERAL_OUTPUT_FILE))
    apps_map = {}

    if existing:
        for app in existing.get("apps", []):
            merge_app_into_map(apps_map, app)
        base_meta = {k: existing.get(k, v) for k, v in GENERAL_BASE_META.items()}
    else:
        base_meta = GENERAL_BASE_META

    for repo_url in GENERAL_REPOS:
        print(f"[*] Scraping (general): {repo_url}")
        data = fetch_json(repo_url)
        if not data:
            continue
        for app in data.get("apps", []):
            merge_app_into_map(apps_map, app)

    write_json(GENERAL_OUTPUT_FILE, build_source(base_meta, existing, apps_map))


def build_fastsign():
    print("\n=== Building fastsign.json ===")
    existing = load_output_file(os.path.join(OUTPUT_DIR, FASTSIGN_OUTPUT_FILE))
    apps_map = {}

    if existing:
        for app in existing.get("apps", []):
            merge_app_into_map(apps_map, app)
        base_meta = {k: existing.get(k, v) for k, v in FASTSIGN_BASE_META.items()}
    else:
        base_meta = FASTSIGN_BASE_META

    print(f"[*] Scraping fastsign: {FASTSIGN_SOURCE_URL}")
    data = fetch_json(FASTSIGN_SOURCE_URL)
    if data:
        for app in data.get("apps", []):
            merge_app_into_map(apps_map, app)

    write_json(FASTSIGN_OUTPUT_FILE, build_source(base_meta, existing, apps_map))


def main():
    build_selected()
    build_general()
    build_fastsign()
    print("\n[+] All sources synchronized.")


if __name__ == "__main__":
    main()
