import os

from dotenv import load_dotenv

from . import channels
from . import settings

load_dotenv()

stage = os.environ.get("STAGE", "dev")

config_dict = {
    "dev": {
        "guilds": [
            channels.GENEKOGAN_GUILD_ID,
            channels.ABRAHAM_BOTDEV_GUILD_ID,
            channels.ABRAHAM_GUILD_ID,
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.ABRAHAM_BOTDEV_ABRAHAM,
            channels.ABRAHAM_BOTDEV_GENERAL,
            channels.ABRAHAM_EDEN,
            channels.ABRAHAM_CORE_EDEN,
            channels.ABRAHAM_DEVS_GENERAL, 
            channels.ABRAHAM_DEVS_DEV,
            channels.ABRAHAM_DEVS_SOCIAL,
        ],
    },
    "prod": {
        "guilds": [
            channels.GENEKOGAN_GUILD_ID,
            channels.MARS_COLLEGE_GUILD_ID,
            channels.ABRAHAM_GUILD_ID,
            channels.BRAINDROPS_GUILD_ID,
            channels.DEADAVATARS_GUILD_ID,
            channels.VIRTUALBEINGS_GUILD_ID,
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.MARS_2023_EDEN,
            channels.MARS_AI,
            channels.MARS_2024_AI,
            channels.MARS_2024_AI_BOTS,
            channels.MARS_STUDY_AI,
            channels.ABRAHAM_DEVS_BOTS,
            channels.ABRAHAM_DEVS_GENERAL, 
            channels.ABRAHAM_DEVS_DEV,
            channels.ABRAHAM_DEVS_SOCIAL,
            channels.ABRAHAM_EDEN,
            channels.ABRAHAM_CORE_EDEN,
            channels.BRAINDROPS_STABLEDIFFUSION,
            channels.DEADAVATARS_GARDENOFEDEN,
            channels.VIRTUALBEINGS_EDEN,
        ],
    },
}
