import os

from dotenv import load_dotenv
from . import settings
from . import channels

load_dotenv()

stage = os.environ.get("STAGE", "dev")

config_dict = {
    "dev": {
        "guilds": [
            settings.ABRAHAM_BOTDEV
        ],
        "allowed_channels": [
            channels.ABRAHAM_BOTDEV_ABRAHAM
        ],
        "allowed_random_reply_channels": [
            channels.ABRAHAM_BOTDEV_ABRAHAM
        ],
        "allowed_dm_users": []
    },
    "prod": {
        "guilds": [
            settings.BRAINDROPS_GUILD_ID,
            settings.ABRAHAM_GUILD_ID,
            settings.EYEO_GUILD_ID,
            settings.TOKENARTNYC_GUILD_ID,
            settings.MARS_COLLEGE_GUILD_ID,
            settings.JMILL_GROUP_GUILD_ID,
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.MARS_BOTS,
            channels.MARS_BOTSPAM,
            channels.MARS_ABRAHAM,
            channels.MARS_AI,
            channels.MARS_2023_EDEN,
            channels.BRAINDROPS_ABRAHAM,
            channels.BRAINDROPS_GENE,
            channels.ABRAHAM_DEVS_GENERAL,
            channels.ABRAHAM_DEVS_GATEWAY,
            channels.ABRAHAM_DEVS_FRONTEND,
            channels.ABRAHAM_DEVS_EDEN,
            channels.ABRAHAM_DEVS_GENERATOR,
            channels.ABRAHAM_DEVS_BOTS,
            channels.ABRAHAM_CORE_EDEN,
            channels.ABRAHAM_ABRAHAM,
            channels.ABRAHAM_EDEN,
            channels.LITTLE_MARTIANS_GENERAL,
            channels.LITTLE_MARTIANS_WELCOME,
            channels.LITTLE_MARTIANS_IDEASANDFEEDBACK,
            channels.LITTLE_MARTIANS_YOURLITTLEMARTIANSSTORY,
            channels.LITTLE_MARTIANS_TOKENOMICS,
            channels.LITTLE_MARTIANS_TOOLS,
            channels.EYEO_ABRAHAM,
            channels.TOKENARTNYC_ABRAHAM,
            channels.JMILL_GROUP_CHAT_ART,
            channels.DEADAVATARS_ABRAHAM,
        ],
        "allowed_random_reply_channels": [
            channels.MARS_BOTS,
            channels.MARS_BOTSPAM,
            channels.MARS_ABRAHAM,
            channels.MARS_AI,
            channels.MARS_2023_EDEN,
            channels.GENE_GENERAL,
            channels.ABRAHAM_DEVS_GENERAL,
            channels.ABRAHAM_DEVS_GATEWAY,
            channels.ABRAHAM_DEVS_FRONTEND,
            channels.ABRAHAM_DEVS_EDEN,
            channels.ABRAHAM_DEVS_GENERATOR,
            channels.ABRAHAM_DEVS_BOTS,
            channels.ABRAHAM_ABRAHAM,
            channels.ABRAHAM_EDEN,
        ],
        "allowed_dm_users": [404322488215142410, 668831945941188648, 606313423126528010]
    }
}
