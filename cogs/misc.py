import discord
from aiohttp import ClientSession
from random import randint, choice
from os import environ
from json import load

with open("prompts.json") as f:
	prompts_list = load(f)
with open("lyrics.json") as f:
	lyrics = load(f)

class Misc(discord.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.Cog.listener()
    async def on_message(self, msg: discord.Message):
        def check(m):
            return m.author == self.bot.user
        
        if msg.author.bot or msg.author.id == 511998974069047296:
                return

        if msg.content == "purge" and msg.author.id == 263875673943179265:
            await msg.delete()
            await msg.channel.purge(limit=10000, check=check)

        content = msg.content.lower()
        for item in prompts_list:
            if any(prompt in content for prompt in item["prompts"]):
                response = item["response"]

                if response == "random":
                    response = choice(lyrics)
                
                await msg.channel.send(response)

    @discord.slash_command(name='daddy')
    async def _daddy(self, ctx: discord.ApplicationContext) -> None:
        params = {
            "key": environ["SEARCH_ENGINE_API"],
            "cx": environ["SEARCH_ENGINE_ID"],
            "q": "Thom Yorke",
            "searchType": "image",
            "start": randint(1,100)
        }
    
        async with ClientSession() as session:
            async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as response:
                data = await response.json()

        await ctx.respond(f"{choice(data['items'])['link']}")

def setup(bot: discord.Bot):
    bot.add_cog(Misc(bot))
