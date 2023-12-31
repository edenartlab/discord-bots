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
            channels.KOJII_INTERNAL_GUILD_ID,
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.ABRAHAM_BOTDEV_ABRAHAM,
            channels.ABRAHAM_BOTDEV_GENERAL,
            channels.ABRAHAM_EDEN,
            channels.ABRAHAM_CORE_EDEN,
            channels.KOJII_INTERNAL_CHARACTERBRANDWIP
        ],
    },
    "prod": {
        "guilds": [
            channels.GENEKOGAN_GUILD_ID,
            channels.ABRAHAM_GUILD_ID,
            channels.KOJII_INTERNAL_GUILD_ID,
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.ABRAHAM_DEVS_BOTS,
            channels.ABRAHAM_EDEN,
            channels.ABRAHAM_CORE_EDEN,
            channels.KOJII_INTERNAL_CHARACTERBRANDWIP
        ],
    },
}
