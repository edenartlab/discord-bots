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
            channels.LITTLEMARTIANS_GUILD_ID,
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
            channels.LITTLE_MARTIANS_GENERAL,
            channels.LITTLE_MARTIANS_WELCOME,
            channels.LITTLE_MARTIANS_IDEASANDFEEDBACK,
            channels.LITTLE_MARTIANS_YOURLITTLEMARTIANSSTORY,
            channels.LITTLE_MARTIANS_TOKENOMICS,
            channels.LITTLE_MARTIANS_TOOLS,
            channels.ABRAHAM_DEVS_BOTSPAM
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
            channels.LITTLEMARTIANS_GUILD_ID
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
            channels.LITTLE_MARTIANS_GENERAL,
            channels.LITTLE_MARTIANS_WELCOME,
            channels.LITTLE_MARTIANS_IDEASANDFEEDBACK,
            channels.LITTLE_MARTIANS_YOURLITTLEMARTIANSSTORY,
            channels.LITTLE_MARTIANS_TOKENOMICS,
            channels.LITTLE_MARTIANS_TOOLS,
            channels.ABRAHAM_DEVS_BOTSPAM
        ],
    },
}
