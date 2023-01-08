import asyncio
import re
import os
import random
from dataclasses import dataclass
from typing import Optional

import discord
import requests
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
from marsbots_eden.eden import get_file_update
from marsbots_eden.eden import poll_creation_queue
from marsbots_eden.eden import request_creation
from marsbots_eden.models import SignInCredentials
from marsbots_eden.models import SourceSettings
from marsbots_eden.models import StableDiffusionConfig

from . import config
from . import settings
from . import channels

# MINIO_URL = "https://{}/{}".format(os.getenv("MINIO_URL"), os.getenv("BUCKET_NAME"))
MINIO_URL = "https://{}/{}".format(os.getenv("MINIO_URL"), "creations-stg")
GATEWAY_URL = "https://gateway-test.abraham.ai"  # os.getenv("GATEWAY_URL")
EDEN_API_KEY = os.getenv("EDEN_API_KEY")
EDEN_API_SECRET = os.getenv("EDEN_API_SECRET")

CONFIG = config.config_dict[config.stage]
ALLOWED_GUILDS = CONFIG["guilds"]
ALLOWED_CHANNELS = CONFIG["allowed_channels"]


@dataclass
class GenerationLoopInput:
    gateway_url: str
    minio_url: str
    start_bot_message: str
    source: SourceSettings
    config: any
    message: discord.Message
    is_video_request: bool = False
    prefer_gif: bool = True
    refresh_interval: int = 2
    parent_message: discord.Message = None


class LerpModal(discord.ui.Modal):
    def __init__(self, bot, refresh_callback, loop_input, **kwargs) -> None:
        super().__init__(**kwargs)
        self.bot = bot
        self.refresh_callback = refresh_callback
        self.loop_input = loop_input
        self.add_item(discord.ui.InputText(label="Short Input"))

    async def callback(self, interaction: discord.Interaction):
        ctx = await self.bot.get_application_context(interaction)
        await ctx.defer()
        text_input1 = self.loop_input.config.text_input
        text_input2 = self.children[0].value
        interpolation_texts = [text_input1, text_input2]
        seed1 = self.loop_input.config.seed
        seed2 = random.randint(1, 1e8)
        interpolation_seeds = [seed1, seed2]
        width = self.loop_input.config.width
        height = self.loop_input.config.height
        n_frames = 60
        steps = self.loop_input.config.steps
        self.loop_input.config = StableDiffusionConfig(
            mode="interpolate",
            stream=True,
            stream_every=1,
            text_input=text_input1,
            interpolation_texts=interpolation_texts,
            interpolation_seeds=interpolation_seeds,
            n_frames=n_frames,
            width=width,
            height=height,
            steps=steps,
        )
        self.loop_input.is_video_request = True
        await self.refresh_callback(loop_input=self.loop_input, reroll_seed=False)


class CreationActionButtons(discord.ui.View):
    def __init__(
        self,
        *items,
        bot,
        creation_sha,
        refresh_callback,
        loop_input: GenerationLoopInput,
        timeout=180,
    ):
        super().__init__(*items, timeout=timeout)
        self.bot = bot
        self.creation_sha = creation_sha
        self.refresh_callback = refresh_callback
        self.loop_input = loop_input

    async def feedback(self, stat, interaction):
        ctx = await self.bot.get_application_context(interaction)
        await ctx.defer()
        requests.post(
            self.loop_input.gateway_url + "/update_stats",
            json={
                "creation": self.creation_sha,
                "stat": stat,
                "opperation": "increase",
                "address": interaction.user.id,
            },
        )

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.blurple)
    async def refresh(self, button, interaction):
        ctx = await self.bot.get_application_context(interaction)
        await ctx.defer()
        await self.refresh_callback(
            loop_input=self.loop_input,
        )

    @discord.ui.button(label="Lerp It")
    async def lerp(self, button, interaction):
        await interaction.response.send_modal(
            LerpModal(
                title="Lerp It",
                bot=self.bot,
                refresh_callback=self.refresh_callback,
                loop_input=self.loop_input,
            )
        )

    @discord.ui.button(emoji="🔥", style=discord.ButtonStyle.red)
    async def burn(self, button, interaction):
        await self.feedback("burn", interaction)

    @discord.ui.button(label="🙌", style=discord.ButtonStyle.green)
    async def praise(self, button, interaction):
        await self.feedback("praise", interaction)
        self.stop()


class HuaqiangbeiCog(commands.Cog):
    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot
        self.eden_credentials = SignInCredentials(
            apiKey=EDEN_API_KEY, apiSecret=EDEN_API_SECRET
        )

    async def generation_loop(
        self,
        loop_input: GenerationLoopInput,
    ):
        gateway_url = loop_input.gateway_url
        minio_url = loop_input.minio_url
        start_bot_message = loop_input.start_bot_message
        parent_message = loop_input.parent_message
        message = loop_input.message
        source = loop_input.source
        config = loop_input.config
        refresh_interval = loop_input.refresh_interval
        is_video_request = loop_input.is_video_request
        prefer_gif = loop_input.prefer_gif

        try:
            task_id = await request_creation(
                gateway_url, self.eden_credentials, source, config
            )
            current_sha = None
            while True:
                result, file, sha = await poll_creation_queue(
                    gateway_url, minio_url, task_id, is_video_request, prefer_gif
                )
                if sha != current_sha:
                    current_sha = sha
                    message_update = self.get_message_update(result)
                    await self.edit_message(
                        message,
                        start_bot_message,
                        message_update,
                        file_update=file,
                    )
                if result["status"] == "complete":
                    file, sha = await get_file_update(
                        result, minio_url, is_video_request, prefer_gif
                    )
                    view = CreationActionButtons(
                        bot=self.bot,
                        creation_sha=sha,
                        loop_input=loop_input,
                        refresh_callback=self.refresh_callback,
                    )
                    if parent_message:
                        new_message = await parent_message.reply(
                            start_bot_message,
                            files=[file],
                            view=None,
                        )
                    else:
                        new_message = await message.channel.send(
                            start_bot_message,
                            files=[file],
                            view=None,
                        )
                    view.loop_input.parent_message = new_message
                    await message.delete()
                    return
                await asyncio.sleep(refresh_interval)

        except Exception as e:
            await self.edit_message(message, start_bot_message, f"Error: {e}")

    async def refresh_callback(
        self,
        loop_input: GenerationLoopInput,
        reroll_seed: bool = True,
    ):
        loop_input.message = await loop_input.parent_message.reply(
            loop_input.start_bot_message,
        )
        if reroll_seed:
            loop_input.config.seed = random.randint(1, 1e8)
        await self.generation_loop(loop_input)

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message) -> None:
        print("RECEIVE MESSAGE")
        try:

            print("ON ", message.channel.id)

            if (
                message.channel.id in ALLOWED_CHANNELS
                and message.author.id != self.bot.user.id
                and message.attachments
            ):
                ctx = await self.bot.get_context(message)
                source = self.get_source(ctx)

                print("JUMP", message.jump_url)

                for attachment in message.attachments:

                    print("CONTENT", message.content)
                    
                    # parse message for number in beginning of string
                    init_img_strength = re.search(r"^\d+", message.content)

                    config = StableDiffusionConfig(
                        mode="remix",
                        stream=True,
                        stream_every=1,
                        text_input="remix",
                        uc_text="poorly drawn face, ugly, tiling, out of frame, extra limbs, disfigured, deformed body, blurry, blurred, watermark, text, grainy, signature, cut off, draft",
                        init_image_data=attachment.url,
                        width=1280,
                        height=720,
                        sampler="euler", 
                        steps=100,
                        init_image_strength=0.2,
                        seed=random.randint(1, 1e8)
                    )

                    start_bot_message = f"**Remix** by <@!{ctx.author.id}> at {message.jump_url}\n"
                    channel = self.bot.get_channel(channels.MARS_2023_HIGHLIGHTS_AI)
                    message = await channel.send(start_bot_message)

                    generation_loop_input = GenerationLoopInput(
                        gateway_url=GATEWAY_URL,
                        minio_url=MINIO_URL,
                        message=message,
                        start_bot_message=start_bot_message,
                        source=source,
                        config=config,
                        is_video_request=False,
                        prefer_gif=False
                    )
                    await self.generation_loop(generation_loop_input)


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

    def get_dimensions(self, aspect_ratio, large):
        if aspect_ratio == "square" and large:
            width, height = 768, 768
        elif aspect_ratio == "square" and not large:
            width, height = 512, 512
        elif aspect_ratio == "landscape" and large:
            width, height = 896, 640
        elif aspect_ratio == "landscape" and not large:
            width, height = 640, 384
        elif aspect_ratio == "portrait" and large:
            width, height = 640, 896
        elif aspect_ratio == "portrait" and not large:
            width, height = 384, 640
        return width, height

    def perm_check(self, ctx):
        if ctx.channel.id not in ALLOWED_CHANNELS:
            return False
        return True

    def get_source(self, ctx):
        source = SourceSettings(
            author_id=int(ctx.author.id),
            author_name=str(ctx.author),
            guild_id=int(ctx.guild.id),
            guild_name=str(ctx.guild),
            channel_id=int(ctx.channel.id),
            channel_name=str(ctx.channel),
        )
        return source

    def get_message_update(self, result):
        status = result["status"]
        if status == "failed":
            return "_Server error: Eden task failed_"
        elif status in "pending":
            return "_Warming up, please wait._"
        elif status in "starting":
            return "_Creation is starting_"
        elif status == "running":
            progress = int(100 * result["progress"])
            return f"_Creation is **{progress}%** complete_"
        elif status == "complete":
            return "_Creation is **100%** complete_"

    async def edit_interaction(
        self,
        ctx,
        start_bot_message,
        message_update,
        file_update=None,
    ):
        message_content = f"{start_bot_message}\n{message_update}"
        if file_update:
            await ctx.edit(content=message_content, file=file_update)
        else:
            await ctx.edit(content=message_content)

    async def edit_message(
        self,
        message: discord.Message,
        start_bot_message: str,
        message_update: str,
        file_update: Optional[discord.File] = None,
    ) -> discord.Message:
        message_content = f"{start_bot_message}\n{message_update}"
        await message.edit(content=message_content)
        if file_update:
            await message.edit(files=[file_update], attachments=[])


def setup(bot: commands.Bot) -> None:
    bot.add_cog(HuaqiangbeiCog(bot))
