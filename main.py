import discord
import os
from discord import ApplicationContext
from dotenv import load_dotenv
import json

load_dotenv()
TOKEN = os.environ["TOKEN"]

URL = "https://api.hypixel.net/skyblock/auctions?page={}"

intents = discord.Intents.all()
bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    cogs = bot.cogs.keys()

    for guild in bot.guilds:
        path = f"settings/{guild.id}.json"
        
        try:
            with open(path) as f:
                settings = json.load(f)
        except:
            await on_guild_join(guild)
            continue

        # cleans old
        for k in settings.keys():
            if not k in cogs:
                settings.pop(k)

        #adds new
        for k in cogs:
            if not k in settings.keys():
                settings[k] = True

        with open(path, "w") as f:
            json.dump(settings, f, indent=2)

    print("rdy")

@bot.event
async def on_guild_join(guild: discord.Guild):
    data = {k: True for k in bot.cogs.keys()}
    
    with open(f"settings/{guild.id}.json", "w") as f:
        json.dump(data, f, indent=2)

# idk if i should keep - seems unnecessary
@bot.event
async def on_guild_leave(guild: discord.Guild):
    os.remove(f"settings/{guild.id}.json")

@bot.event
async def on_application_command_error(ctx: ApplicationContext, exception):
	await ctx.respond(exception)

@bot.slash_command(description="Modify bot settings")
async def settings(ctx: discord.ApplicationContext):
    with open(f"settings/{ctx.guild_id}.json") as f:
        settings = json.load(f)
    embed = discord.Embed(title="Settings",
                      description="Enable / Disable features based on group.",
                      colour=0x39f98c)
    
    for name, cog in bot.cogs.items():
        enabled = "✅" if settings[name] else "❌"
        commands = '\n'.join(command.qualified_name for command in cog.get_commands())
        embed.add_field(name=f"{enabled} {name} {cog.emoji}",
                        value=f'{cog.description}\n\n{commands}',
                        inline=True) 
        
    await ctx.respond(embed=embed)

if __name__ == "__main__":
	extensions = [f'cogs.{file[:-3]}' for file in os.listdir('cogs') if file.endswith('.py')]
	bot.load_extensions(*extensions)

	bot.run(TOKEN)