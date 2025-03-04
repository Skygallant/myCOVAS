import json
import os
import requests
import random
import threading
import time
import pygame
import hashlib
import sys

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
under_attack_timer = None
BGS_timer = None
Song_timer = None
Old_BGS = ""
journal_lines = ""

# Open log file
log_file = open(os.path.join(plugin_dir, "myCOVAS.log"), "w", encoding="utf-8", buffering=1)
# Redirect stdout and stderr
sys.stdout = log_file
sys.stderr = log_file

# Load API Key and Voice ID from external files
def load_file_content(filename):
    try:
        with open(os.path.join(plugin_dir, filename), "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Error: {filename} not found. Make sure it exists in the plugin directory.")
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
            print(f"Failed to generate speech: {response.status_code} - {response.text}")
            return
    
    pygame.mixer.Sound(audio_path).play()  # Play voice line at full volume
    pygame.time.wait(int(pygame.mixer.Sound(audio_path).get_length() * 1000))
    adjust_music_volume(desired_volume)  # Restore music volume

def play_random_music():
    """Continuously plays random music files from the current music directory using pygame."""
    global current_music_dir, music_queue, Song_timer
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

def switch_to_combat_music():
    """Switches the music directory to combat music for 2 minutes."""
    global current_music_dir, under_attack_timer
    if current_music_dir != COMBAT_MUSIC_DIR:
        current_music_dir = COMBAT_MUSIC_DIR
        mixtape_swap()
    if under_attack_timer:
        under_attack_timer.cancel()
    under_attack_timer = threading.Timer(120, restore_music)
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
        print(f"Failed to retrieve data: {response.status_code}")
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

def journal_entry(cmdr, is_beta, system, station, entry, state):
    """Handles incoming journal events."""
    global journal_lines
    event_type = entry.get("event")
    if event_type == "UnderAttack":
        switch_to_combat_music()
    elif event_type in journal_lines:
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
    global journal_lines, ELEVENLABS_API_URL, BGS_timer, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, BGS_SYSTEM_ID, BGS_SYSTEM_NAME, CACHE_DIR, MUSIC_DIR, COMBAT_MUSIC_DIR, current_music_dir

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
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(MUSIC_DIR, exist_ok=True)
    os.makedirs(COMBAT_MUSIC_DIR, exist_ok=True)

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

    print("Stopping myCOVAS plugin...")

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

    print("myCOVAS plugin has been stopped.")
