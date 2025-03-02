# myCOVAS
A full AI-driven COVAS replacement and music player for Elite: Dangerous by FDev

# Requirements
an elevenlabs account.
a working local Python installation with pip.
a copy of EDMC running from source.

# Features
Currently, myCOVAS features a reactionary commentary-like feature, similar to the regular covas, that can be customised to say anything in relation to any journal entry. It also has a music player, with auto-ducking for when the AI wants to say something, and it will change to combat music where appropriate. BGS monitoring of a single system is supported, myCOVAS will give a news report every 5 minutes (as long as the news report would be different from the previous).

# Instructions
1. Install Python
2. do `pip install pygame`
3. make sure you run EDMC from source given these instructions <https://github.com/EDCD/EDMarketConnector/wiki/Running-from-source>
4. Open EDMC, go to the plugins tab, and open your plugins folder. Then do `git clone https://github.com/Skygallant/myCOVAS.git`
5. Some setup is required in the form of 4 .txt files:
    * API.txt - Needs an [elevenlabs api](https://elevenlabs.io/app/settings/api-keys) key to generate the voices
    * BGS.txt - This is the system ID for a single system that has BGS you want to monitor. The ID can be obtained from a <https://spansh.co.uk> url, for example, `10477373803` is the ID for the [Sol system](https://spansh.co.uk/system/10477373803)
    * BGS_Name.txt - This is simply with the name of the system, or the name you want myCOVAS to call the system (useful for colonised systems).
    * VoiceID.txt - This is for the voice id of the elevenlabs voice you want to use. It can be obtained from an "ID" copy button wehn you view a voice's details.
6. Place .mp3 files into the music folder (generated after first run), these will play while you play the game.
7. Place .mp3 files into the combat folder (generated after first run), these will play for some time once your ship receives hostile fire.
8. Customise lines.json as you see fit. Use <https://elite-journal.readthedocs.io> for how to name the journal titles.