import os
import json
import requests

# --- CONFIGURATION ---
# Add your target repos and the specific bundle identifiers you want to pull from them.
CONFIG = {
    "https://github.com/titouan336/Spotify-AltStoreRepo-mirror/blob/main/source.json": [
        "com.spotify.client",
        "com.spotify.client.patched"
    ]
}

REPO_FILE = "source.json"

def get_raw_url(url):
    """Converts standard GitHub blob URLs to raw content URLs if needed."""
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

def load_local_repo():
    """Loads your local repository file."""
    if os.path.exists(REPO_FILE):
        with open(REPO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError(f"Could not find {REPO_FILE} in the working directory.")

def merge_app_data(local_app, remote_app):
    """
    Merges historical versions into your local data array.
    Keeps your custom app names, descriptions, icons, and permissions intact.
    """
    # 1. Map local versions to avoid duplicates
    existing_versions = {
        (v.get("version"), str(v.get("buildVersion"))): v 
        for v in local_app.get("versions", [])
    }
    
    # 2. Append new versions from the scraped source
    for remote_ver in remote_app.get("versions", []):
        v_key = (remote_ver.get("version"), str(remote_ver.get("buildVersion")))
        
        if v_key not in existing_versions:
            print(f"[+] Found new version {v_key[0]} (Build {v_key[1]}) for {local_app['bundleIdentifier']}")
            local_app["versions"].append(remote_ver)
            
    # Sort versions descending by date so AltStore sees the latest release at the top
    local_app["versions"].sort(key=lambda x: x.get("date", ""), reverse=True)
    
    # 3. Synchronize top-level download keys with the absolute newest version found
    if local_app["versions"]:
        latest = local_app["versions"][0]
        local_app["version"] = latest.get("version")
        local_app["versionDate"] = latest.get("date", "").split("T")[0] # Keeps YYYY-MM-DD format
        local_app["size"] = latest.get("size")
        local_app["downloadURL"] = latest.get("downloadURL")
        
    return local_app

def main():
    local_repo = load_local_repo()
    
    # Create a quick map of your existing apps by their bundle ID
    local_apps_map = {app["bundleIdentifier"]: app for app in local_repo.get("apps", [])}
    
    for repo_url, target_bundle_ids in CONFIG.items():
        target_url = get_raw_url(repo_url)
        print(f"[*] Scraping source: {target_url}")
        
        try:
            response = requests.get(target_url, timeout=15)
            response.raise_for_status()
            remote_data = response.json()
        except Exception as e:
            print(f"[-] Skipped repo due to connection error: {e}")
            continue
            
        for remote_app in remote_data.get("apps", []):
            bid = remote_app.get("bundleIdentifier")
            if bid not in target_bundle_ids:
                continue
                
            if bid in local_apps_map:
                print(f"[*] Merging versions for existing app: {bid}")
                local_apps_map[bid] = merge_app_data(local_apps_map[bid], remote_app)
            else:
                print(f"[+] Initializing new tracked app structure: {bid}")
                # Baseline cloning for apps you haven't manually styled yet
                local_apps_map[bid] = remote_app

    # Re-apply the updated map back to the primary json structure
    local_repo["apps"] = list(local_apps_map.values())
    
    with open(REPO_FILE, "w", encoding="utf-8") as f:
        json.dump(local_repo, f, indent=2, ensure_ascii=False)
    print("[+] Synchronization complete.")

if __name__ == "__main__":
    main()
