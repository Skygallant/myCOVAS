import json
import os
import requests
import random
import threading
import time
import pygame
import hashlib
import sys
import math
import subprocess
import logging

try:
    # Optional EDMCOverlay integration (overlay on top of the game)
    import edmcoverlay
    EDM_COVAS_OVERLAY_AVAILABLE = True
except Exception:
    edmcoverlay = None
    EDM_COVAS_OVERLAY_AVAILABLE = False

EDMC_VERSION = "4.0"
desired_volume = 40
plugin_dir = os.path.dirname(os.path.abspath(__file__))
ELEVENLABS_API_KEY = ""
ELEVENLABS_VOICE_ID = ""
BGS_SYSTEM_ID = ""
BGS_SYSTEM_NAME = ""
ELEVENLABS_API_URL = ""
music_queue = []
CACHE_DIR = ""
MUSIC_DIR = ""
COMBAT_MUSIC_DIR = ""
current_music_dir = ""
CODEX_DIR = ""
music_enabled = True
under_attack_timer = None
BGS_timer = None
Song_timer = None
Old_BGS = ""
journal_lines = ""
codex_missing_cache = {}
codex_coordinates_cache = {}
codex_overlay_client = None
codex_overlay_last_text = ""
codex_overlay_msgid = "mycovas-codex-main"
codex_overlay_center_x = 640
codex_overlay_center_y = 40
codex_overlay_timer = None
codex_target_system = ""
CANONN_API_BASE = "https://us-central1-canonn-api-236217.cloudfunctions.net/query"
CANONN_DUMPR_BASE = "https://storage.googleapis.com/canonn-downloads/dumpr"

# Set up dedicated logger for this plugin
logger = logging.getLogger("myCOVAS")
logger.setLevel(logging.INFO)
if not logger.handlers:
    try:
        log_path = os.path.join(plugin_dir, "myCOVAS.log")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)
        # Avoid duplicating messages into EDMC's main log unless desired
        logger.propagate = False
    except Exception as e:
        # Fall back silently; we don't want logging setup to break the plugin
        print(f"Failed to set up myCOVAS logger: {e}", file=sys.__stderr__)

# Load API Key and Voice ID from external files
def load_file_content(filename):
    try:
        with open(os.path.join(plugin_dir, filename), "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        logger.error(f"{filename} not found. Make sure it exists in the plugin directory.")
        return None

def process_voice_line(text):
    """Handles playing the voice line with proper caching and volume control."""
    pygame.mixer.stop()  # Stop any currently playing voice lines
    adjust_music_volume(desired_volume * 0.35)  # Reduce music volume by 35%
    hashed_text = hashlib.sha256(text.encode()).hexdigest()
    audio_path = os.path.join(CACHE_DIR, f"{hashed_text}.mp3")
    
    if not os.path.exists(audio_path):
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.9
            }
        }
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        response = requests.post(ELEVENLABS_API_URL, json=payload, headers=headers)
        if response.status_code == 200:
            with open(audio_path, "wb") as audio_file:
                audio_file.write(response.content)
        else:
            logger.error(f"Failed to generate speech: {response.status_code} - {response.text}")
            return
    
    pygame.mixer.Sound(audio_path).play()  # Play voice line at full volume
    pygame.time.wait(int(pygame.mixer.Sound(audio_path).get_length() * 1000))
    adjust_music_volume(desired_volume)  # Restore music volume

def play_random_music():
    """Continuously plays random music files from the current music directory using pygame."""
    global current_music_dir, music_queue, Song_timer, music_enabled

    if not music_enabled:
        return

    if not music_queue:
        music_queue = [f for f in os.listdir(current_music_dir) if f.endswith(".mp3")]
        random.shuffle(music_queue)  # Shuffle only when queue is empty

    if music_queue:
        music_file = music_queue.pop()
        pygame.mixer.music.load(os.path.join(current_music_dir, music_file))
        pygame.mixer.music.play()
        Song_timer = threading.Timer(pygame.mixer.Sound(os.path.join(current_music_dir, music_file)).get_length(), play_random_music)
        Song_timer.daemon = True
        Song_timer.start()
        
def mixtape_swap():
    """faciliates swapping between different playlists"""
    global Song_timer, music_queue
    if Song_timer:
        Song_timer.cancel()
        Song_timer = None
    music_queue = []
    pygame.mixer.music.fadeout(1000)  # Fadeout the current song
    play_random_music()

def toggle_music():
    """Toggles music playback on or off."""
    global music_enabled, Song_timer

    if music_enabled:
        music_enabled = False
        if Song_timer:
            Song_timer.cancel()
            Song_timer = None
        pygame.mixer.music.stop()
        logger.info("Music playback disabled via /music chat command.")
    else:
        music_enabled = True
        logger.info("Music playback enabled via /music chat command.")
        play_random_music()
        adjust_music_volume(desired_volume)

def switch_to_combat_music():
    """Switches the music directory to combat music for 2 minutes."""
    global current_music_dir, under_attack_timer
    if current_music_dir != COMBAT_MUSIC_DIR:
        current_music_dir = COMBAT_MUSIC_DIR
        mixtape_swap()
    if under_attack_timer:
        under_attack_timer.cancel()
    under_attack_timer = threading.Timer(180, restore_music)
    under_attack_timer.start()

def restore_music():
    """Restores the normal music directory."""
    global current_music_dir
    current_music_dir = MUSIC_DIR
    mixtape_swap()

def BGS_update():
    """Polls Spansh API and determines BGS news."""
    global BGS_timer, BGS_SYSTEM_ID, Old_BGS, BGS_SYSTEM_NAME
    # Construct the API URL
    url = f"https://spansh.co.uk/api/system/{BGS_SYSTEM_ID}"
    # Send the GET request
    response = requests.get(url)
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON data
        Spansh = response.json()
    else:
        logger.error(f"Failed to retrieve Spansh data: {response.status_code}")
    minor_factions = Spansh["record"].get("minor_faction_presences", [])
    if Old_BGS == "" or Old_BGS != minor_factions:
        Old_BGS = Spansh["record"].get("minor_faction_presences", [])
        process_voice_line(f"News update for the {BGS_SYSTEM_NAME} system.")
        for faction in Old_BGS:
            process_voice_line(f"{faction['name']} currently control {faction['influence']:.0%} of the system and are in a state of {faction['state']}")
    
    BGS_timer = threading.Timer(300, BGS_update)
    BGS_timer.daemon = True
    BGS_timer.start()
    

def adjust_music_volume(change):
    """Adjusts the volume of the currently playing music in pygame."""
    volume = change / 100.0  # Convert percentage to float (0.0 to 1.0)
    pygame.mixer.music.set_volume(volume)

def _update_codex_overlay():
    """Apply the current codex overlay text and visibility state to EDMCOverlay."""
    global codex_overlay_client, codex_overlay_last_text

    if not EDM_COVAS_OVERLAY_AVAILABLE or not codex_overlay_client:
        return

    try:
        # Nothing to show
        if not codex_overlay_last_text:
            return

        codex_overlay_client.send_message(
            codex_overlay_msgid,
            codex_overlay_last_text,
            "#998040",
            codex_overlay_center_x,
            codex_overlay_center_y,
            ttl=30,
            size="large",
        )
    except Exception as e:
        logger.error(f"Error updating codex overlay: {e}")


def set_codex_overlay_text(text):
    """Set the desired overlay text and refresh the overlay."""
    global codex_overlay_last_text
    codex_overlay_last_text = text or ""
    # Do not force-show the overlay here; /obj controls visibility.


def copy_to_clipboard(text):
    """Copy the given text to the system clipboard (Windows: uses clip)."""
    try:
        subprocess.run("clip", input=text, text=True, check=True)
        logger.info(f"Copied to clipboard: {text}")
    except Exception as e:
        logger.error(f"Failed to copy to clipboard: {e}")


def nearest_codex_worker(cmdr, star_pos, star_system, show_overlay, copy_system_flag, source_event):
    """Background worker: finds nearest undiscovered codex entry and optionally shows/copies it."""
    global codex_target_system
    try:
        result = get_nearest_undiscovered_codex(cmdr, star_pos)
        if result:
            codex_name, codex_system, distance = result
            logger.info(
                f"{source_event} in {star_system}: nearest undiscovered codex entry is "
                f"{codex_name} at {codex_system} ({distance:.2f} ly away)."
            )
            codex_target_system = codex_system or ""
            set_codex_overlay_text(codex_name)
            if copy_system_flag and codex_system:
                copy_to_clipboard(codex_system)
            if show_overlay:
                _update_codex_overlay()
        else:
            logger.info(f"{source_event} in {star_system}: no undiscovered codex entries found for {cmdr}.")
            codex_target_system = ""
            set_codex_overlay_text("")
            if show_overlay:
                _update_codex_overlay()
    except Exception as e:
        logger.error(f"Error computing nearest undiscovered codex for {cmdr}: {e}")

def fetch_missing_codex_entries(cmdr):
    """Fetches and caches missing (undiscovered) codex entries for a commander."""
    global codex_missing_cache
    if not cmdr:
        return []

    if cmdr in codex_missing_cache:
        return codex_missing_cache[cmdr]

    try:
        url = f"{CANONN_API_BASE}/missing/codex"
        params = {"cmdr": cmdr}
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            logger.error(f"Failed to fetch missing codex entries for {cmdr}: {response.status_code} - {response.text}")
            return []
        data = response.json()

        # API currently returns a list of entries; fall back to dict->values for robustness
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = list(data.values())
        else:
            logger.error(f"Unexpected missing/codex response type for {cmdr}: {type(data)}")
            return []

        codex_missing_cache[cmdr] = entries
        return entries
    except Exception as e:
        logger.error(f"Error fetching missing codex entries for {cmdr}: {e}")
        return []

def fetch_codex_coordinates(entryid, hud_category):
    """Fetches and caches all system coordinates for a codex entry from the Canonn dumpr CSV."""
    global codex_coordinates_cache
    if not entryid or not hud_category:
        return []

    key = (str(entryid), str(hud_category))
    if key in codex_coordinates_cache:
        return codex_coordinates_cache[key]

    systems = []

    # Try to load from local cache file first
    csv_text = None
    try:
        if CODEX_DIR:
            local_filename = f"{hud_category}_{entryid}.csv"
            local_path = os.path.join(CODEX_DIR, local_filename)
            if os.path.exists(local_path):
                with open(local_path, "r", encoding="utf-8") as f:
                    csv_text = f.read()
    except Exception as e:
        logger.error(f"Error reading cached coordinates CSV for entry {entryid} / {hud_category}: {e}")

    try:
        if csv_text is None:
            csv_url = f"{CANONN_DUMPR_BASE}/{hud_category}/{entryid}.csv"
            response = requests.get(csv_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to fetch coordinates CSV for entry {entryid} / {hud_category}: {response.status_code}")
                codex_coordinates_cache[key] = []
                return []
            csv_text = response.text

            # Cache the CSV text to disk for future use
            try:
                if CODEX_DIR:
                    os.makedirs(CODEX_DIR, exist_ok=True)
                    local_filename = f"{hud_category}_{entryid}.csv"
                    local_path = os.path.join(CODEX_DIR, local_filename)
                    with open(local_path, "w", encoding="utf-8") as f:
                        f.write(csv_text)
            except Exception as e:
                logger.error(f"Error caching coordinates CSV for entry {entryid} / {hud_category}: {e}")

        for raw_line in csv_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 4:
                continue
            system_name = parts[0]
            try:
                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])
            except ValueError:
                continue
            systems.append((system_name, x, y, z))

        codex_coordinates_cache[key] = systems
        return systems
    except Exception as e:
        logger.error(f"Error fetching coordinates CSV for entry {entryid} / {hud_category}: {e}")
        codex_coordinates_cache[key] = []
        return []

def get_nearest_undiscovered_codex(cmdr, star_pos):
    """
    Uses the Canonn Undiscovered Codex methodology to find the nearest
    undiscovered codex entry to the given commander position.

    Returns a tuple (codex_name, system_name, distance_ly) or None if unavailable.
    """
    if not star_pos or len(star_pos) != 3:
        return None

    try:
        px, py, pz = star_pos
    except (TypeError, ValueError):
        return None

    entries = fetch_missing_codex_entries(cmdr)
    if not entries:
        return None

    nearest_name = None
    nearest_system = None
    nearest_distance = None

    for entry in entries:
        entryid = entry.get("entryid")
        hud_category = entry.get("hud_category")
        english_name = entry.get("english_name") or entry.get("name")
        systems = fetch_codex_coordinates(entryid, hud_category)
        if not systems:
            continue

        for system_name, x, y, z in systems:
            dx = x - px
            dy = y - py
            dz = z - pz
            distance = math.sqrt(dx * dx + dy * dy + dz * dz)

            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_name = english_name
                nearest_system = system_name

    if nearest_name and nearest_system is not None and nearest_distance is not None:
        logger.info(f"Nearest undiscovered codex for {cmdr}: {nearest_name} at {nearest_system} ({nearest_distance:.2f} ly)")
        return nearest_name, nearest_system, nearest_distance

    return None

def journal_entry(cmdr, is_beta, system, station, entry, state):
    """Handles incoming journal events."""
    global journal_lines
    event_type = entry.get("event")

    # Toggle music when the commander sends "/music" to the local chat channel
    if event_type == "SendText":
        message = entry.get("Message", "").strip()
        to = entry.get("To", "").lower()
        if to == "local":
            lower_msg = message.lower()
            if lower_msg == "/music":
                toggle_music()
                return
            if lower_msg == "/obj":
                # On-demand: compute and display nearest undiscovered codex entry
                star_pos = state.get("StarPos")
                star_system = system or state.get("SystemName")
                if not star_pos or len(star_pos) != 3:
                    logger.warning("Cannot resolve nearest codex target: no current StarPos available.")
                    return
                threading.Thread(
                    target=nearest_codex_worker,
                    args=(cmdr, star_pos, star_system, True, False, "/obj"),
                    daemon=True,
                ).start()
                return
            if lower_msg == "/desto":
                # On-demand: compute nearest undiscovered codex entry and copy system name
                star_pos = state.get("StarPos")
                star_system = system or state.get("SystemName")
                if not star_pos or len(star_pos) != 3:
                    logger.warning("Cannot resolve nearest codex destination: no current StarPos available.")
                    return
                threading.Thread(
                    target=nearest_codex_worker,
                    args=(cmdr, star_pos, star_system, False, True, "/desto"),
                    daemon=True,
                ).start()
                return

    if event_type == "UnderAttack":
        switch_to_combat_music()
    if event_type in journal_lines:
        text_options = journal_lines.get(event_type, [])
        if text_options:
            text = random.choice(text_options)
        if text:
            process_voice_line(text)

def plugin_start3(plugin_dir):
    """Called when the plugin is loaded in Python 3 mode."""
    return plugin_start(plugin_dir)

def plugin_start(plugin_dir):
    """Called when the plugin is loaded."""
    global journal_lines, ELEVENLABS_API_URL, BGS_timer, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, BGS_SYSTEM_ID, BGS_SYSTEM_NAME, CACHE_DIR, MUSIC_DIR, COMBAT_MUSIC_DIR, current_music_dir, CODEX_DIR
    global codex_overlay_client, codex_overlay_center_x, codex_overlay_center_y

    ELEVENLABS_API_KEY = load_file_content("API.txt")
    ELEVENLABS_VOICE_ID = load_file_content("VoiceID.txt")
    BGS_SYSTEM_ID = load_file_content("BGS.txt")
    BGS_SYSTEM_NAME = load_file_content("BGS_Name.txt")

    # Validate API key and voice ID
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        raise ValueError("Missing API Key or Voice ID. Please ensure API.txt and VoiceID.txt are properly set up.")
  
    ELEVENLABS_API_URL = ""f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

    # Ensure cache and music directories exist
    CACHE_DIR = os.path.join(plugin_dir, "cache")
    MUSIC_DIR = os.path.join(plugin_dir, "music")
    COMBAT_MUSIC_DIR = os.path.join(plugin_dir, "combat")
    CODEX_DIR = os.path.join(plugin_dir, "codex")
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(MUSIC_DIR, exist_ok=True)
    os.makedirs(COMBAT_MUSIC_DIR, exist_ok=True)
    os.makedirs(CODEX_DIR, exist_ok=True)

    # Register Modern Overlay grouping via its public API when available.
    # This keeps overlay_groupings.json in sync without manual edits.
    try:
        from overlay_plugin.overlay_api import define_plugin_group, PluginGroupingError  # type: ignore

        try:
            # Top-level plugin group + matching prefixes
            define_plugin_group(
                plugin_group="myCOVAS",
                matching_prefixes=["mycovas-"],
            )
            # Codex target group: anchored at top, ModernOverlay handles centering
            define_plugin_group(
                plugin_group="myCOVAS",
                id_prefix_group="Codex Target",
                id_prefixes=["mycovas-codex-"],
                id_prefix_group_anchor="center",
            )
            logger.info("Registered ModernOverlay grouping for myCOVAS.")
        except PluginGroupingError as e:
            logger.error(f"Failed to register ModernOverlay grouping: {e}")
    except Exception:
        # If ModernOverlay isn't installed or API isn't available, skip gracefully.
        logger.info("EDMC-ModernOverlay API not available; skipping overlay grouping registration.")

    # Initialise EDMCOverlay client if available so we can show nearest-codex info
    if EDM_COVAS_OVERLAY_AVAILABLE and edmcoverlay is not None:
        try:
            codex_overlay_client = edmcoverlay.Overlay()
            logger.info("EDMCOverlay client initialised for myCOVAS.")
        except Exception as e:
            logger.error(f"Failed to initialise EDMCOverlay client: {e}")

    current_music_dir = MUSIC_DIR

    # Load the journal entry mappings
    lines_json_path = os.path.join(plugin_dir, "lines.json")
    with open(lines_json_path, "r", encoding="utf-8") as file:
        journal_lines = json.load(file)["JournalEntryTexts"]
      
    # Initialize pygame mixer
    pygame.mixer.init()
    play_random_music()
    adjust_music_volume(desired_volume)
  
    # Start the BGS update timer
    BGS_timer = threading.Timer(5, BGS_update)
    BGS_timer.daemon = True
    BGS_timer.start()
  
    return "myCOVAS"

def plugin_stop():
    """Called when the plugin is unloaded."""
    global BGS_timer, under_attack_timer, Song_timer

    logger.info("Stopping myCOVAS plugin...")

    # Stop music and quit Pygame safely
    pygame.mixer.music.stop()
    pygame.mixer.quit()

    if BGS_timer:
        BGS_timer.cancel()
        BGS_timer = None

    if under_attack_timer:
        under_attack_timer.cancel()
        under_attack_timer = None

    if Song_timer:
        Song_timer.cancel()
        Song_timer = None

    logger.info("myCOVAS plugin has been stopped.")
