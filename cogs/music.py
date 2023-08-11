import discord
from discord.ext import commands
from discord.ext.pages import Paginator
from discord import ApplicationContext, ApplicationCommandError
from yt_dlp import YoutubeDL
import asyncio
from async_timeout import timeout


YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    # 'no_warnings': True,
    # 'ignoreerrors': True,
    "default_search": "auto",
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
    "options": "-vn",
}


class SongQueue(asyncio.Queue):  # bc voice client already in use
    def __init__(self, loop, voice_client):
        super().__init__()
        self.current = None
        self.loop = False
        self.volume = 0.1

        self.next = asyncio.Event()

        self.voice_client = voice_client
        self.audio_player = loop.create_task(self.player())

    async def player(self):
        while True:
            if not self.loop or not self.current:
                try:
                    async with timeout(180):
                        self.current = await self.get()
                except:
                    await self.voice_client.disconnect()

            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(self.current["url"], **FFMPEG_OPTS),
                volume=self.volume,
            )
            self.voice_client.play(source, after=self.play_next)

            embed = self.current['embed']
            embed.set_author(name="Now Playing")

            await self.current["ctx"].respond(embed=embed)

            await self.next.wait()

    def play_next(self, error=None):
        if error:
            raise ApplicationCommandError(str(error))

        self.next.set()

    async def purge(self):
        while not self.empty():
            await self.get()

    async def clear(self):
        await self.purge()
        self.voice_client.stop()

    def all(self):
        queue = [self.current] + list(self.__dict__['_queue'])
        return queue

class SkipButton(discord.ui.Button):
    def __init__(self, member, total: int, voice_client: discord.VoiceProtocol):
        super().__init__()

        self.voice_client = voice_client
        
        if member.guild_permissions.administrator or total == 1:
            self.skip()
        else:
            self.label = f'1/{self.total} skip'

        self.total = total
        self.ids = [member.id]

    def skip(self):
        self.voice_client.stop()
        self.label = 'Skipped'
        self.disabled = True

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user

        if not member.id in self.ids: 
            self.ids.append(member.id)
            count = len(self.ids)
            
            if member.guild_permissions.administrator or count == self.total:
                self.skip()
            else:
                self.label = f'{count}/{self.total} skip'

            view = discord.ui.View()
            view.add_item(self)

            await interaction.response.edit_message(view=view)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.description = "Music player features"
        self.emoji = "🎵"

        self.queues = {}


    async def cog_before_invoke(self, ctx: ApplicationContext):
        await ctx.defer()

        if not hasattr(ctx.author.voice, "channel"):
            raise ApplicationCommandError("join vc dumbass")
        
        ctx.queue = self.queues[ctx.guild_id] if ctx.guild_id in self.queues else None
        

    @discord.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id != self.bot.user.id:
            return

        if after.self_deaf == False:
            await after.channel.guild.change_voice_state(
                channel=after.channel, self_deaf=True
            )

        # If disconnected
        if not after.channel:
            self.queues[member.guild.id].audio_player.cancel()
            del self.queues[member.guild.id]


    async def connect(self, ctx: ApplicationContext):
        member = ctx.author
        channel = member.voice.channel
        voice_client = ctx.voice_client

        if voice_client:
            if voice_client.channel != channel:
                # check if busy
                if member.guild_permissions.move_members or not (voice_client.is_playing() or voice_client.is_paused()):
                    await voice_client.move_to(channel)
                    return "okay i moved to ur vc"
                else:
                    raise ApplicationCommandError("i'm busy")
            else:
                return "I'm already in ur vc silly"
        else:
            self.queues[ctx.guild_id] = SongQueue(self.bot.loop, await channel.connect())
            ctx.queue = self.queues[ctx.guild_id]
            return "okay i connected to ur vc"


    @discord.slash_command(name="connect")
    async def _connect(self, ctx: ApplicationContext):
        response = await self.connect(ctx)
        await ctx.respond(response)
    @discord.slash_command(name="join")
    async def _join(self, ctx: ApplicationContext):
        await self._connect(ctx)


    @discord.slash_command(name="disconnect")
    async def _disconnect(self, ctx: ApplicationContext):
        # Does user have to be in same vc as bot to dc?
        if ctx.voice_client:  # if connected
            await ctx.voice_client.disconnect()
            await ctx.respond("\;(")
        else:
            await ctx.respond("Bot not in a vc silly head")
    @discord.slash_command(name="leave")
    async def _leave(self, ctx: ApplicationContext):
        await self._disconnect(ctx)


    @discord.slash_command(name="play")
    async def _play(self, ctx: ApplicationContext, song):
        # Checks vc
        await self.connect(ctx)

        # Filter not working like shorts
        try:
            with YoutubeDL(YDL_OPTS) as ydl:
                info = ydl.extract_info(song, download=False)
        except:
            raise ApplicationCommandError("Error")

        async def process_info(info):
            data = {
                'embed': discord.Embed(title=info['title'],
                                       url=info['webpage_url'],
                                       description=f'By [{info["uploader"]}]({info["uploader_url"]})'
                                       ).set_image(url=info['thumbnail']),
                'url': info['url'],
                'ctx': ctx
            }

            await ctx.queue.put(data)

            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                embed = data['embed']
                embed.set_author(name="Added to queue")

                await ctx.respond(embed=embed)

        if info["extractor"] != 'youtube:tab':
            if info["extractor"] == "youtube:search":
                info = info["entries"][0]
            info['entries'] = [info]
            
        for entry in info['entries']:
            await process_info(entry)


    @discord.slash_command(name="stop")
    async def _stop(self, ctx: ApplicationContext):
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.queue.loop = False
            await ctx.queue.clear()
            await ctx.respond("okay stopped")
        else:
            raise ApplicationCommandError("not playing anything lil bro")
    @discord.slash_command(name='clear')
    async def _clear(self, ctx: ApplicationContext):
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await ctx.queue.clear()
            await ctx.respond("okay stopped")
        else:
            raise ApplicationCommandError("not playing anything lil bro")


    @discord.slash_command(name="loop")
    async def _loop(self, ctx: ApplicationContext):
        ctx.queue.loop = not ctx.queue.loop
        await ctx.respond(f"set loop to `{ctx.queue.loop}`")

    
    @discord.slash_command(name="skip")
    async def _skip(self, ctx: ApplicationContext):
        voice_client = ctx.voice_client

        if voice_client.is_playing() or voice_client.is_paused():
            view = discord.ui.View()

            total = len(voice_client.channel.members)
            view.add_item(SkipButton(ctx.author, round(total/3), voice_client))

            await ctx.respond(embed=ctx.queue.current['embed'], view=view)
            # ctx.voice_client.stop()
            # await ctx.respond("okay song skipped")
        else:
            raise ApplicationCommandError("not playing anything lil bro")

    @discord.slash_command(name="volume")
    async def _volume(
        self,
        ctx: ApplicationContext,
        value: discord.Option(int, min_value=0, max_value=200),
    ):
        ctx.queue.volume = value / 100
        ctx.voice_client.source.volume = value / 100
        await ctx.respond(f"okay set volume to `{value}%`")

    @discord.slash_command(name="queue", description="Displays the queue")
    async def _queue(self, ctx: discord.ApplicationContext) -> None:
        if not ctx.guild_id in self.queues:
            raise ApplicationCommandError('No queue initialized')
        if not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            raise ApplicationCommandError('Nothing playing lil bro')
        
        pages = [entry['embed'] for entry in ctx.queue.all()]
        paginator = Paginator(pages=pages)

        await paginator.respond(ctx.interaction, ephemeral=False)

    
    @_clear.before_invoke
    @_stop.before_invoke
    @_loop.before_invoke
    @_skip.before_invoke
    @_volume.before_invoke
    async def before_invoke(self, ctx: ApplicationContext):
        voice_client = ctx.voice_client

        if voice_client:
            if not ctx.author.voice.channel == voice_client.channel:
                raise ApplicationCommandError("you need to be in same vc")
        else:
            raise ApplicationCommandError("not even connected lil bro")


def setup(bot: discord.Bot):
    bot.add_cog(Music(bot))
