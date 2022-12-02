import asyncio
import logging
import os
import random
from dataclasses import dataclass
from typing import Optional

import discord
from discord.ext import commands
from marsbots.discord_utils import get_discord_messages
from marsbots.discord_utils import get_reply_chain
from marsbots.discord_utils import is_mentioned
from marsbots.discord_utils import replace_bot_mention
from marsbots.discord_utils import replace_mentions_with_usernames
from marsbots.language_models import complete_text
from marsbots.language_models import OpenAIGPT3LanguageModel
from marsbots.models import ChatMessage
from marsbots.util import hex_to_rgb_float
from marsbots_eden.eden import get_file_update
from marsbots_eden.eden import poll_creation_queue
from marsbots_eden.eden import request_creation
from marsbots_eden.models import SourceSettings
from marsbots_eden.models import EdenClipXConfig

from . import config
from . import prompts
from . import settings

GATEWAY_URL = "https://gateway-test.abraham.ai" # os.getenv("GATEWAY_URL")
MINIO_URL = "http://{}/{}".format(os.getenv("MINIO_URL"), os.getenv("BUCKET_NAME"))

CONFIG = config.config_dict[config.stage]
ALLOWED_GUILDS = CONFIG["guilds"]
ALLOWED_CHANNELS = CONFIG["allowed_channels"]
ALLOWED_RANDOM_REPLY_CHANNELS = CONFIG["allowed_random_reply_channels"]
ALLOWED_DM_USERS = CONFIG["allowed_dm_users"]


@dataclass
class GenerationLoopInput:
    gateway_url: str
    minio_url: str
    start_bot_message: str
    source: SourceSettings
    config: any
    message: discord.Message
    is_video_request: bool = False
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
        width = self.loop_input.config.width
        height = self.loop_input.config.height
        n_interpolate = 12
        ddim_steps = self.loop_input.config.ddim_steps
        self.loop_input.config = StableDiffusionConfig(
            mode="interpolate",
            text_input=text_input1,
            interpolation_texts=interpolation_texts,
            n_interpolate=n_interpolate,
            width=width,
            height=height,
            ddim_steps=ddim_steps,
            fixed_code=True,
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

    # @discord.ui.button(label="Lerp It")
    # async def lerp(self, button, interaction):
    #     await interaction.response.send_modal(
    #         LerpModal(
    #             title="Lerp It",
    #             bot=self.bot,
    #             refresh_callback=self.refresh_callback,
    #             loop_input=self.loop_input,
    #         )
    #     )

    @discord.ui.button(emoji="🔥", style=discord.ButtonStyle.red)
    async def burn(self, button, interaction):
        await self.feedback("burn", interaction)

    @discord.ui.button(label="🙌", style=discord.ButtonStyle.green)
    async def praise(self, button, interaction):
        await self.feedback("praise", interaction)
        self.stop()


class Abraham(commands.Cog):
    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot
        self.language_model = OpenAIGPT3LanguageModel(
            engine=settings.GPT3_ENGINE,
            temperature=settings.GPT3_TEMPERATURE,
            frequency_penalty=settings.GPT3_FREQUENCY_PENALTY,
            presence_penalty=settings.GPT3_PRESENCE_PENALTY,
        )

    @commands.slash_command(guild_ids=ALLOWED_GUILDS)
    async def complete(
        self,
        ctx,
        prompt: discord.Option(str, description="Prompt", required=True),
        max_tokens: discord.Option(
            int,
            description="Maximum number of tokens to generate",
            required=False,
            default=100,
        ),
    ):
        if not self.perm_check(ctx):
            await ctx.respond("This command is not available in this channel.")
            return
        await ctx.defer()
        try:
            completion = await complete_text(self.language_model, prompt, max_tokens)
            formatted = f"**{prompt}**{completion}"
            await ctx.respond(formatted)
        except Exception as e:
            logging.error(e)
            await ctx.respond("Error completing text - " + str(e))

    # @commands.slash_command(
    #     guild_ids=ALLOWED_GUILDS,
    # )
    # async def create(
    #     self,
    #     ctx,
    #     text_input: discord.Option(str, description="Prompt", required=True),
    #     image_url: discord.Option(
    #         str,
    #         description="Image URL",
    #         required=False,
    #         default="",
    #     ),
    #     color_target_hex: discord.Option(
    #         str,
    #         description="Color Target Hex Code",
    #         required=False,
    #         default="#000000",
    #     ),
    #     color_loss_f: discord.Option(
    #         float,
    #         description="Color Loss Percentage",
    #         required=False,
    #         default=0.0,
    #     ),
    #     color_target_pixel_fraction: discord.Option(
    #         float,
    #         description="Color Target Pixel Fraction",
    #         required=False,
    #         default=0.75,
    #     ),
    #     n_permuted_prompts_to_add: discord.Option(
    #         str,
    #         description="Number of Permuted Prompts to Add",
    #         required=False,
    #         default=-1,
    #     ),
    #     aspect_ratio: discord.Option(
    #         str,
    #         choices=[
    #             discord.OptionChoice(name="square", value="square"),
    #             discord.OptionChoice(name="landscape", value="landscape"),
    #             discord.OptionChoice(name="portrait", value="portrait")
    #         ],
    #         required=False,
    #         default="landscape"
    #     ),
    #     large: discord.Option(bool, description="Larger resolution, ~2.25x more pixels", required=False, default=False)
    # ):

    #     if not self.perm_check(ctx):
    #         await ctx.respond("This command is not available in this channel.")
    #         return

    #     if settings.CONTENT_FILTER_ON:
    #         if not OpenAIGPT3LanguageModel.content_safe(text_input):
    #             await ctx.respond(
    #                 f"Content filter triggered, <@!{ctx.author.id}>. Please don't make me draw that. If you think it was a mistake, modify your prompt slightly and try again.",
    #             )
    #             return

    #     source = self.get_source(ctx)

    #     width, height = self.get_dimensions(aspect_ratio, large)

    #     config = EdenClipXConfig(
    #         text_input=text_input,
    #         image_url=image_url,
    #         n_permuted_prompts_to_add=n_permuted_prompts_to_add,
    #         color_rgb_target=hex_to_rgb_float(color_target_hex),
    #         color_loss_f=color_loss_f,
    #         color_target_pixel_fraction=color_target_pixel_fraction,
    #         width=width,
    #         height=height,
    #     )

    #     start_bot_message = f"**{text_input}** - <@!{ctx.author.id}>\n\n"
    #     #await ctx.respond(start_bot_message)
    #     await ctx.respond("Starting to create...")
    #     message = await ctx.channel.send(start_bot_message)

    #     generation_loop_input = GenerationLoopInput(
    #         gateway_url=GATEWAY_URL,
    #         minio_url=MINIO_URL,
    #         message=message,
    #         start_bot_message=start_bot_message,
    #         source=source,
    #         config=config,
    #     )
    #     await self.generation_loop(generation_loop_input)

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
        try:
            task_id = await request_creation(gateway_url, source, config)
            while True:
                result, file = await poll_creation_queue(
                    gateway_url,
                    minio_url,
                    task_id,
                    is_video_request,
                )
                message_update = self.get_message_update(result)

                await self.edit_message(
                    message,
                    start_bot_message,
                    message_update,
                    file_update=file,
                )

                if result["status"] == "complete":
                    file, sha = await get_file_update(
                        result,
                        minio_url,
                        is_video_request,
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
        try:
            if (
                message.channel.id not in ALLOWED_CHANNELS
                or message.author.id == self.bot.user.id
                or message.author.bot
            ):
                return

            trigger_reply = is_mentioned(message, self.bot.user) or (
                message.channel.id in ALLOWED_RANDOM_REPLY_CHANNELS
                and random.random() < settings.RANDOM_REPLY_PROBABILITY
            )

            if trigger_reply:
                ctx = await self.bot.get_context(message)
                async with ctx.channel.typing():
                    prompt = await self.format_prompt(ctx, message)
                    completion = await complete_text(
                        self.language_model,
                        prompt,
                        max_tokens=80,
                        stop=["<", "\n\n"],
                        use_content_filter=True,
                    )
                    await message.reply(completion.strip())

        except Exception as e:
            print(f"Error: {e}")
            await message.reply(":)")

    def message_preprocessor(self, message: discord.Message) -> str:
        message_content = replace_bot_mention(message.content, only_first=True)
        message_content = replace_mentions_with_usernames(message_content, message.mentions)
        message_content = message_content.strip()
        return message_content

    async def format_prompt(
        self,
        ctx: commands.context,
        message: discord.Message,
    ) -> str:
        last_message_content = self.message_preprocessor(message)
        topic_idx = self.get_similar_topic_idx(last_message_content)
        topic_prefix = prompts.topics[topic_idx]["prefix"]
        last_messages = await get_discord_messages(ctx.channel, 1)
        reply_chain = await get_reply_chain(ctx, message, depth=6)
        if reply_chain:
            reply_chain = self.format_reply_chain(reply_chain)
        last_message_text = str(
            ChatMessage(
                f"{self.message_preprocessor(last_messages[0])}",
                "M",
                deliniator_left="<",
                deliniator_right=">",
            ),
        ).strip()
        prompt = topic_prefix
        if reply_chain:
            prompt += f"{reply_chain}\n"
        prompt += "\n".join(
            [
                last_message_text,
                "<Abraham>",
            ],
        )
        return prompt

    def format_reply_chain(self, messages):
        reply_chain = []
        for message in messages:
            if message.author.id == self.bot.user.id:
                sender_name = "Abraham"
            else:
                sender_name = "M"
            reply_chain.append(
                ChatMessage(
                    content=f"{self.message_preprocessor(message)}",
                    sender=sender_name,
                    deliniator_left="<",
                    deliniator_right=">",
                ),
            )
        return "\n".join([str(message).strip() for message in reply_chain])

    def get_similar_topic_idx(self, query: str) -> int:
        docs = [topic["document"] for topic in prompts.topics]
        res = self.language_model.document_search(query, docs)
        return self.language_model.most_similar_doc_idx(res)

    async def get_start_gen_message(self, ctx):
        async with ctx.channel.typing():
            completion = await complete_text(
                self.language_model,
                prompts.start_prompt,
                max_tokens=100,
                stop=["\n", "\n\n"],
            )
            return completion

    def get_dimensions(self, aspect_ratio, large):
        if aspect_ratio == 'square' and large:
            width, height = 768, 768
        elif aspect_ratio == 'square' and not large:
            width, height = 512, 512
        elif aspect_ratio == 'landscape' and large:
            width, height = 896, 640
        elif aspect_ratio == 'landscape' and not large:
            width, height = 640, 384
        elif aspect_ratio == 'portrait' and large:
            width, height = 640, 896
        elif aspect_ratio == 'portrait' and not large:
            width, height = 384, 640
        return width, height

    def perm_check(self, ctx):
        if ctx.channel.id not in ALLOWED_CHANNELS:
            return False
        return True

    def get_source(self, ctx):
        source = SourceSettings(
            origin="discord",
            author=int(ctx.author.id),
            author_name=str(ctx.author),
            guild=int(ctx.guild.id),
            guild_name=str(ctx.guild),
            channel=int(ctx.channel.id),
            channel_name=str(ctx.channel),
        )
        return source

    def get_message_update(self, result):
        status = result["status"]
        if status == "failed":
            return "_Server error: Eden task failed_"
        elif status in "pending":
            return "_Creation is pending_"
        elif status == "queued":
            queue_idx = result["status_code"]
            return f"_Creation is #{queue_idx} in queue_"
        elif status == "running":
            progress = result["status_code"]
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
    bot.add_cog(Abraham(bot))
