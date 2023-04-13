import os

from dotenv import load_dotenv

from . import channels
from . import settings

load_dotenv()

stage = os.environ.get("STAGE", "dev")

config_dict = {
    "dev": {
        "guilds": [
            channels.MARS_COLLEGE_GUILD_ID,
            channels.GENEKOGAN_GUILD_ID,
        ],
        "allowed_channels": [
            channels.MARS_2023_HIGHLIGHTS,
            channels.MARS_2023_HIGHLIGHTS_AI,
            channels.GENE_GENERAL,
        ],
    },
    "prod": {
        "guilds": [
            channels.MARS_COLLEGE_GUILD_ID,
            channels.GENEKOGAN_GUILD_ID,
        ],
        "allowed_channels": [
            channels.MARS_2023_HIGHLIGHTS,
            channels.MARS_2023_HIGHLIGHTS_AI,
            channels.GENE_GENERAL,
        ],
    },
}
