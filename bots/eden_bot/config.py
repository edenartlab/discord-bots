import os

from dotenv import load_dotenv

from . import channels
from . import settings

load_dotenv()

stage = os.environ.get("STAGE", "dev")

config_dict = {
    "dev": {
        "guilds": [settings.ABRAHAM_BOTDEV],
        "allowed_channels": [channels.ABRAHAM_BOTDEV_ABRAHAM],
    },
    "prod": {
        "guilds": [
            settings.GENEKOGAN_GUILD_ID,
            settings.MARS_COLLEGE_GUILD_ID,
            settings.ABRAHAM_GUILD_ID,
            settings.BRAINDROPS_GUILD_ID,
            settings.DEADAVATARS_GUILD_ID,
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.MARS_2023_EDEN,
            channels.MARS_AI,
            channels.ABRAHAM_DEVS_BOTS,
            channels.ABRAHAM_EDEN,
            channels.ABRAHAM_CORE_EDEN,
            channels.BRAINDROPS_STABLEDIFFUSION,
            channels.DEADAVATARS_GARDENOFEDEN,
        ],
    },
}
