import os

import discord
from aleph_alpha_client import AlephAlphaClient
from aleph_alpha_client import AlephAlphaModel
from aleph_alpha_client import CompletionRequest
from aleph_alpha_client import ImagePrompt
from aleph_alpha_client import Prompt
from discord.ext import commands
from marsbots.discord_utils import is_mentioned
from marsbots.discord_utils import replace_bot_mention
from marsbots.discord_utils import replace_mentions_with_usernames
from marsbots.language_models import OpenAIGPT3LanguageModel
from marsbots_eden.eden import generation_loop
from marsbots_eden.eden import SourceSettings
from marsbots_eden.eden import StableDiffusionSettings

from . import config
from . import settings


minio_url = "http://{}/{}".format(os.getenv("MINIO_URL"), os.getenv("BUCKET_NAME"))
gateway_url = os.getenv("GATEWAY_URL")
magma_token = os.getenv("MAGMA_API_KEY")

CONFIG = config.config_dict[config.stage]
ALLOWED_GUILDS = CONFIG["guilds"]
ALLOWED_CHANNELS = CONFIG["allowed_channels"]


class EdenCog(commands.Cog):
    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot
        self.language_model = OpenAIGPT3LanguageModel(
            engine=settings.GPT3_ENGINE,
            temperature=settings.GPT3_TEMPERATURE,
            frequency_penalty=settings.GPT3_FREQUENCY_PENALTY,
            presence_penalty=settings.GPT3_PRESENCE_PENALTY,
        )
        self.magma_model = AlephAlphaModel(
            AlephAlphaClient(host="https://api.aleph-alpha.com", token=magma_token),
            model_name="luminous-extended",
        )

    @commands.slash_command(
        guild_ids=ALLOWED_GUILDS,
    )
    async def dream(
        self,
        ctx,
        text_input: discord.Option(str, description="Prompt", required=True),
        aspect_ratio: discord.Option(
            str,
            choices=[
                discord.OptionChoice(name="square", value="square"),
                discord.OptionChoice(name="landscape", value="landscape"),
                discord.OptionChoice(name="portrait", value="portrait"),
            ],
            required=False,
            default="square",
        ),
    ):

        if not self.perm_check(ctx):
            await ctx.respond("This command is not available in this channel.")
            return

        if settings.CONTENT_FILTER_ON:
            if not OpenAIGPT3LanguageModel.content_safe(text_input):
                await ctx.respond(
                    f"Content filter triggered, <@!{ctx.author.id}>. Please don't make me draw that. If you think it was a mistake, modify your prompt slightly and try again.",
                )
                return

        source = SourceSettings(
            origin="discord",
            author=int(ctx.author.id),
            author_name=str(ctx.author),
            guild=int(ctx.guild.id),
            guild_name=str(ctx.guild),
            channel=int(ctx.channel.id),
            channel_name=str(ctx.channel),
        )

        if aspect_ratio == "square":
            width, height = 512, 512
        elif aspect_ratio == "landscape":
            width, height = 640, 384
        elif aspect_ratio == "portrait":
            width, height = 384, 640

        steps = 166
        plms = True
        upscale = False

        config = StableDiffusionSettings(
            text_input=text_input,
            width=width,
            height=height,
            ddim_steps=steps,
            plms=plms,
            C=4,
            f=4 if upscale else 8,
        )

        start_bot_message = f"**{text_input}** - <@!{ctx.author.id}>\n\n"
        await ctx.respond(start_bot_message)

        await generation_loop(
            gateway_url,
            minio_url,
            ctx,
            start_bot_message,
            source,
            config,
            refresh_interval=2,
        )

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message) -> None:
        try:
            if (
                message.channel.id not in ALLOWED_CHANNELS
                or message.author.id == self.bot.user.id
                or message.author.bot
            ):
                return

            trigger_reply = is_mentioned(message, self.bot.user) and message.attachments

            if trigger_reply:
                ctx = await self.bot.get_context(message)
                async with ctx.channel.typing():
                    prompt = self.message_preprocessor(message)
                    if prompt:
                        text_input = 'Question: "{}"\nAnswer:'.format(prompt)
                        prefix = ""
                    else:
                        text_input = "This is a picture of "
                        prefix = text_input
                    url = message.attachments[0].url
                    image = ImagePrompt.from_url(url)
                    magma_prompt = Prompt([image, text_input])
                    request = CompletionRequest(prompt=magma_prompt, maximum_tokens=40)
                    result = self.magma_model.complete(request)
                    response = prefix + result.completions[0].completion.strip(' "')
                    await message.reply(response)

        except Exception as e:
            print(f"Error: {e}")
            await message.reply(":)")

    def message_preprocessor(self, message: discord.Message) -> str:
        message_content = replace_bot_mention(message.content, only_first=True)
        message_content = replace_mentions_with_usernames(
            message_content,
            message.mentions,
        )
        message_content = message_content.strip()
        return message_content

    def perm_check(self, ctx):
        if ctx.channel.id not in ALLOWED_CHANNELS:
            return False
        return True


def setup(bot: commands.Bot) -> None:
    bot.add_cog(EdenCog(bot))
