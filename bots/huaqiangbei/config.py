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
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.MARS_2023_HIGHLIGHTS,
        ],
    },
    "prod": {
        "guilds": [
            channels.GENEKOGAN_GUILD_ID,
            channels.MARS_COLLEGE_GUILD_ID,
        ],
        "allowed_channels": [
            channels.GENE_GENERAL,
            channels.MARS_2023_HIGHLIGHTS,
        ],
    },
}
