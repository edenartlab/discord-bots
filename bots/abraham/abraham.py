import logging
import os
import random

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
from marsbots_eden import EdenClipXSettings
from marsbots_eden import generation_loop
from marsbots_eden import SourceSettings

from . import channels
from . import prompts
from . import settings

gateway_url = os.getenv("GATEWAY_URL")
minio_url = "http://{}/{}".format(os.getenv("MINIO_URL"), os.getenv("BUCKET_NAME"))


class Abraham(commands.Cog):
    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot
        self.language_model = OpenAIGPT3LanguageModel(
            engine=settings.GPT3_ENGINE,
            temperature=settings.GPT3_TEMPERATURE,
            frequency_penalty=settings.GPT3_FREQUENCY_PENALTY,
            presence_penalty=settings.GPT3_PRESENCE_PENALTY,
        )

    @commands.slash_command(guild_ids=settings.GUILD_IDS)
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

    @commands.slash_command(
        guild_ids=settings.GUILD_IDS,
    )
    async def create(
        self,
        ctx,
        text_input: discord.Option(str, description="Prompt", required=True),
        image_url: discord.Option(
            str,
            description="Image URL",
            required=False,
            default="",
        ),
        color_target_hex: discord.Option(
            str,
            description="Color Target Hex Code",
            required=False,
            default="#000000",
        ),
        color_loss_f: discord.Option(
            float,
            description="Color Loss Percentage",
            required=False,
            default=0.0,
        ),
        color_target_pixel_fraction: discord.Option(
            float,
            description="Color Target Pixel Fraction",
            required=False,
            default=0.75,
        ),
        n_permuted_prompts_to_add: discord.Option(
            str,
            description="Number of Permuted Prompts to Add",
            required=False,
            default=-1,
        ),
        width: discord.Option(str, description="Width", required=False, default=768),
        height: discord.Option(str, description="Height", required=False, default=512),
    ):

        if not self.perm_check(ctx):
            await ctx.respond("This command is not available in this channel.")
            return

        await ctx.respond("Starting to create.")

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

        config = EdenClipXSettings(
            text_input=text_input,
            image_url=image_url,
            n_permuted_prompts_to_add=n_permuted_prompts_to_add,
            color_rgb_target=hex_to_rgb_float(color_target_hex),
            color_loss_f=color_loss_f,
            color_target_pixel_fraction=color_target_pixel_fraction,
            width=width,
            height=height,
        )

        start_bot_message = f"Prompt by <@!{ctx.author.id}>: **{text_input}**\n\n"
        bot_message = await ctx.channel.send(start_bot_message)

        await generation_loop(
            gateway_url,
            minio_url,
            source,
            config,
            bot_message,
            bot_message,
            ctx,
            refresh_interval=2,
        )

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message) -> None:
        try:
            if (
                message.channel.id not in channels.ALLOWED_CHANNELS
                or message.author.id == self.bot.user.id
                or message.author.bot
            ):
                return

            trigger_reply = is_mentioned(message, self.bot.user) or (
                message.channel.id in channels.ALLOWED_CHANNELS_RANDOM_REPLY
                and random.random() < channels.RANDOM_REPLY_PROBABILITY
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
        message_content = replace_mentions_with_usernames(
            message_content,
            message.mentions,
        )
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

    def perm_check(self, ctx):
        if ctx.channel.id not in channels.ALLOWED_CHANNELS:
            return False
        return True


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Abraham(bot))
