import discord
import os
from auctions import start
from discord import ApplicationContext
from dotenv import load_dotenv
from multiprocessing import Manager

load_dotenv()
TOKEN = os.environ["TOKEN"]

URL = "https://api.hypixel.net/skyblock/auctions?page={}"

intents = discord.Intents.all()
bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
	await bot.change_presence(status=discord.Status.idle, activity=discord.Game("dating sim"))
	print("ready")

@bot.event
async def on_application_command_error(ctx: ApplicationContext, exception):
	await ctx.respond(exception)

@bot.slash_command()
async def output(ctx: discord.ApplicationContext):
	auctions = bot.auctions
	print(len(auctions))

if __name__ == "__main__":
	manager = Manager()
	bot.auctions = manager.dict()
	start(bot.auctions)

	for file in os.listdir("cogs"):
		if file.endswith(".py"):
			bot.load_extension(f"cogs.{file[:-3]}")
	
	bot.run(TOKEN)