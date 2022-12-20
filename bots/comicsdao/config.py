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
            channels.COMICSDAO_GUILD_ID,
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.ABRAHAM_BOTDEV_ABRAHAM,
            channels.ABRAHAM_BOTDEV_GENERAL,
            channels.ABRAHAM_DEVS_BOTS,
            channels.ABRAHAM_EDEN,
            channels.ABRAHAM_CORE_EDEN,
            channels.COMICSDAO_AI_COMICS,
        ],
    },
    "prod": {
        "guilds": [
            channels.ABRAHAM_GUILD_ID,
            channels.COMICSDAO_GUILD_ID,
        ],
        "allowed_channels": [
            channels.ABRAHAM_DEVS_BOTS,
            channels.ABRAHAM_EDEN,
            channels.ABRAHAM_CORE_EDEN,
            channels.COMICSDAO_AI_COMICS,
        ],
    },
}
