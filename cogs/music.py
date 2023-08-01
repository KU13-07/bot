import discord
from discord import ApplicationContext, ApplicationCommandError
from yt_dlp import YoutubeDL
import asyncio
from async_timeout import timeout

# Auto delete error messages?

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
    def __init__(self, bot, voice_client):
        super().__init__()
        self.voice_client = voice_client

        self.current = None
        self.loop = False
        self.volume = 0.3

        self.next = asyncio.Event()
        self.audio_player = bot.loop.create_task(self.player())

    async def player(self):
        while True:
            # self.voice_client.stop()
            if not self.loop or not self.current:
                try:
                    async with timeout(180):
                        self.current = await self.get()
                except:
                    print("hi")
                    await self.voice_client.disconnect()

            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(self.current["url"], **FFMPEG_OPTS),
                volume=self.volume,
            )
            self.voice_client.play(source, after=self.play_next)

            self.current["embed"].set_author(name="Now Playing")
            await self.current["ctx"].respond(embed=self.current["embed"])

            await self.next.wait()

    def play_next(self, error=None):
        print("done", self.voice_client.is_playing())
        if error:
            raise ApplicationCommandError(str(error))

        self.next.set()

    async def clear(self):
        while not self.empty():
            await self.get()


class Music(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.description = "Music player features"
        self.emoji = "🎵"

        self.queues = {}

    async def cog_before_invoke(self, ctx: ApplicationContext):
        if not hasattr(ctx.author.voice, "channel"):
            raise ApplicationCommandError("join vc dumbass")

    @discord.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id != self.bot.user.id:
            return

        # If disconnected
        if after.self_deaf == False:
            await after.channel.guild.change_voice_state(
                channel=after.channel, self_deaf=True
            )
        if not after.channel:
            print(self.queues)
            self.queues[member.guild.id].audio_player.cancel()
            del self.queues[member.guild.id]
            print(self.queues)

    async def connect(self, ctx: ApplicationContext):
        channel = ctx.author.voice.channel
        voice_client = ctx.voice_client

        if voice_client:
            if voice_client.channel != channel:
                # check if busy
                if not (voice_client.is_playing() or voice_client.is_paused()):
                    await voice_client.move_to(channel)
                    return "okay i moved to ur vc"
                else:
                    raise ApplicationCommandError("i'm busy")
            else:
                return "I'm already in ur vc silly"
        else:
            self.queues[ctx.guild_id] = SongQueue(self.bot, await channel.connect())
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
        await ctx.defer()
        await self.connect(ctx)

        # Filter not working like shorts
        try:
            with YoutubeDL(YDL_OPTS) as ydl:
                info = ydl.extract_info(song, download=False)
        except:
            raise ApplicationCommandError("Error")

        async def process_info(info):
            data = {
                "embed": (
                    discord.Embed(
                        title=info["title"],
                        url=info["webpage_url"],
                        description=f"By [{info['uploader']}]({info['uploader_url']})",
                    ).set_image(url=info["thumbnail"])
                ),
                "url": info["url"],
                "ctx": ctx,
            }

            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                data["embed"].set_author(name="Added to queue")
                await ctx.respond(embed=data["embed"])

            return data

        if info["extractor"] == "youtube:tab":
            for entry in info["entries"]:
                await self.queues[ctx.guild_id].put(await process_info(entry))
        else:
            if info["extractor"] == "youtube:search":
                info = info["entries"][0]
            await self.queues[ctx.guild_id].put(await process_info(info))

    @discord.slash_command(name="stop")
    async def _stop(self, ctx: ApplicationContext):
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            self.queues[ctx.guild_id].loop = False
            await self.queues[ctx.guild_id].clear()
            ctx.voice_client.stop()
            await ctx.respond("okay stopped")
        else:
            raise ApplicationCommandError("not playing anything lil bro")

    @discord.slash_command(name="clear")
    async def _clear(self, ctx: ApplicationContext):
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            self.queues[ctx.guild_id].loop = False
            await self.queues[ctx.guild_id].clear()
            await ctx.respond("okay queue cleared")
        else:
            raise ApplicationCommandError("not playing anything lil bro")

    @discord.slash_command(name="loop")
    async def _loop(self, ctx: ApplicationContext):
        self.queues[ctx.guild_id].loop = not self.queues[ctx.guild_id].loop
        await ctx.respond(f"set loop to `{self.queues[ctx.guild_id].loop}`")

    @discord.slash_command(name="skip")
    async def _skip(self, ctx: ApplicationContext):
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()
            await ctx.respond("okay song skipped")
        else:
            raise ApplicationCommandError("not playing anything lil bro")

    @discord.slash_command(name="volume")
    async def _volume(
        self,
        ctx: ApplicationContext,
        value: discord.Option(int, min_value=0, max_value=200),
    ):
        self.queues[ctx.guild_id].volume = value / 100
        ctx.voice_client.source.volume = value / 100
        await ctx.respond(f"okay set volume to `{value}%`")

    @_stop.before_invoke
    @_clear.before_invoke
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
