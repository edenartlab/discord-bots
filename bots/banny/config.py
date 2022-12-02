import os

from dotenv import load_dotenv

from . import channels
from . import settings

load_dotenv()

stage = os.environ.get("STAGE", "dev")

config_dict = {
    "dev": {
        "guilds": [
            channels.GENEKOGAN_GUILD_ID
        ],
        "allowed_channels": [
            channels.GENE_GENERAL
        ]
    },
    "prod": {
        "guilds": [
            channels.GENEKOGAN_GUILD_ID,
            channels.MARS_COLLEGE_GUILD_ID,
            channels.ABRAHAM_GUILD_ID,
            channels.BRAINDROPS_GUILD_ID,
            channels.DEADAVATARS_GUILD_ID,
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
        ]
    },
}
