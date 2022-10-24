import asyncio
import json
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
from marsbots_eden.eden import poll_clip_queue
from marsbots_eden.eden import request_clip
from marsbots_eden.models import SourceSettings
from marsbots_eden.models import StableDiffusionConfig

from . import config
from . import settings


MINIO_URL = "http://{}/{}".format(os.getenv("MINIO_URL"), os.getenv("BUCKET_NAME"))
GATEWAY_URL = os.getenv("GATEWAY_URL")
MAGMA_TOKEN = os.getenv("MAGMA_API_KEY")


GATEWAY_URL2 = "https://gateway.dev.aws.abraham.fun" 

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



class ImageActionButtons(discord.ui.View):
    def __init__(
        self,
        *items,
        bot,
        image_url,
        magma_callback,
        interrogator_callback,
        timeout=180,
    ):
        super().__init__(*items, timeout=timeout)
        self.bot = bot
        self.image_url = image_url
        self.magma_callback = magma_callback
        self.interrogator_callback = interrogator_callback

    @discord.ui.button(label="Give me a prompt for it")
    async def prompt(self, button, interaction):
        ctx = await self.bot.get_application_context(interaction)
        await ctx.defer()
        response = self.interrogator_callback(self.image_url)
        await interaction.response.send_message(response)

    # @discord.ui.button(label="Ask a question about it")
    # async def ask(self, button, interaction):
    #     await interaction.response.send_modal(
    #         AskModal(
    #             title="Lerp It 222",
    #             bot=self.bot
    #         )
    #     )

    @discord.ui.button(label="Write a poem about it")
    async def poem(self, button, interaction):
        # response = self.magma_callback(
        #     self.image_url,
        #     text_input="A short poem about this picture:",
        #     stop_sequences=[],
        #     maximum_tokens=160,
        #     temperature=0.92
        # )
        ctx = await self.bot.get_application_context(interaction)
        await ctx.defer()
        
        import time
        time.sleep(5)
        response = "hello world"
        await interaction.response.send_message(response)


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
            AlephAlphaClient(host="https://api.aleph-alpha.com", token=MAGMA_TOKEN),
            model_name="luminous-extended",
        )

    @commands.slash_command(guild_ids=ALLOWED_GUILDS)
    async def go(
        self,
        ctx
    ):     
        data = {
            "config": {
                "mode": "interrogate",
                "image_url": "https://cdn.discordapp.com/attachments/1006144058940469268/1011744967653326898/a_painting_of_a_mountain_with_a_lake_below_it_an_art_deco_painting_by_Lawren_Harris_trending_on_behance_crystal_cubism_fauvism_cubism_chillwave_v4.png"
            },
            "sniffer_name": "clip-tools"
        }
        
        await ctx.defer()
        async with ctx.channel.typing():
            result = requests.post(
                f"{GATEWAY_URL}/cliptest",
                json=data
            )       
            result = json.loads(result.content)
            await ctx.respond(result['caption'])
            

    @commands.slash_command(guild_ids=ALLOWED_GUILDS)
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
        large: discord.Option(
            bool,
            description="Larger resolution, ~2.25x more pixels",
            required=False,
            default=False,
        ),
        fast: discord.Option(
            bool,
            description="Fast generation, possibly some loss of quality",
            required=False,
            default=False,
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

        source = self.get_source(ctx)
        width, height = self.get_dimensions(aspect_ratio, large)
        ddim_steps = 15 if fast else 50
        
        config = StableDiffusionConfig(
            mode="generate",
            text_input=text_input,
            width=width,
            height=height,
            ddim_steps=ddim_steps,
            seed=random.randint(1, 1e8),
        )

        start_bot_message = f"**{text_input}** - <@!{ctx.author.id}>\n"
        await ctx.respond("Starting to dream...")
        message = await ctx.channel.send(start_bot_message)

        generation_loop_input = GenerationLoopInput(
            gateway_url=GATEWAY_URL,
            minio_url=MINIO_URL,
            message=message,
            start_bot_message=start_bot_message,
            source=source,
            config=config
        )
        await self.generation_loop(generation_loop_input)

    @commands.slash_command(guild_ids=ALLOWED_GUILDS)
    async def lerp(
        self,
        ctx,
        text_input1: discord.Option(str, description="First prompt", required=True),
        text_input2: discord.Option(str, description="Second prompt", required=True),
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
            if not OpenAIGPT3LanguageModel.content_safe(
                text_input1,
            ) or not OpenAIGPT3LanguageModel.content_safe(text_input2):
                await ctx.respond(
                    f"Content filter triggered, <@!{ctx.author.id}>. Please don't make me draw that. If you think it was a mistake, modify your prompt slightly and try again.",
                )
                return

        source = self.get_source(ctx)

        interpolation_texts = [text_input1, text_input2]
        n_interpolate = 12
        ddim_steps = 25
        width, height = self.get_dimensions(aspect_ratio, False)

        config = StableDiffusionConfig(
            mode="interpolate",
            text_input=text_input1,
            interpolation_texts=interpolation_texts,
            n_interpolate=n_interpolate,
            width=width,
            height=height,
            ddim_steps=ddim_steps,
            seed=random.randint(1, 1e8),
            fixed_code=True,
        )

        start_bot_message = f"**{text_input1}** to **{text_input2}** - <@!{ctx.author.id}>\n"
        await ctx.respond("Lerping...")
        message = await ctx.channel.send(start_bot_message)

        generation_loop_input = GenerationLoopInput(
            gateway_url=GATEWAY_URL,
            minio_url=MINIO_URL,
            message=message,
            start_bot_message=start_bot_message,
            source=source,
            config=config,
            is_video_request=True,
        )
        await self.generation_loop(generation_loop_input)

    def run_interrogator(
        self,
        image_url
    ):
        print('dfhkdsf')
        config = {
            "mode": "interrogate",
            "image_url": image_url
        }
        result = requests.post(
            f"{GATEWAY_URL2}/request_clip",
            json={"config": config, "sniffer_name": "clip-tools"}
        )           
        print("go")                
        print(result.content)
            
        result = json.loads(result.content)
        task_id = result['task_id']
        print("GOT TAKS", task_id)
        return task_id


    def run_magma(
        self,
        image_url,
        text_input,
        stop_sequences,
        maximum_tokens=100,
        temperature=0.5
    ):
        image = ImagePrompt.from_url(image_url)
        magma_prompt = Prompt([image, text_input])
        request = CompletionRequest(
            prompt=magma_prompt,
            maximum_tokens=maximum_tokens,
            temperature=temperature,
            stop_sequences=stop_sequences,
        )
        result = self.magma_model.complete(request)
        response = result.completions[0].completion.strip(' "')
        return response

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
                            view=view,
                        )
                    else:
                        new_message = await message.channel.send(
                            start_bot_message,
                            files=[file],
                            view=view,
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


            self.run_interrogator("http://4.bp.blogspot.com/-gx1tuHXeaSA/Tc2ut4VVvJI/AAAAAAAAAVs/6ND6FL1avvY/s1600/ben-grasso.jpg")

            await message.reply("yo")



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
                    image_url = message.attachments[0].url
                    if prompt:
                        text_input = 'Question: "{}"\nAnswer:'.format(prompt)
                        response = self.run_magma(
                            image_url=image_url, 
                            text_input=text_input,
                            stop_sequences=["Question:", "Answer:"],
                            maximum_tokens=100,
                            temperature=0.5
                        )
                        await message.reply(response)
                    else:
                        view = ImageActionButtons(
                            bot=self.bot,
                            image_url=image_url,
                            magma_callback=self.run_magma,
                            interrogator_callback=self.run_interrogator
                        )
                        await message.reply(
                            "What would you like?",
                            view=view,
                        )

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
    bot.add_cog(EdenCog(bot))
