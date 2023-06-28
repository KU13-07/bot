import discord
from discord import ApplicationContext
from dotenv import load_dotenv
import os
import json
import random
import openai

from aiohttp import ClientSession

load_dotenv()
openai.api_key = os.environ["OPENAI"]
TOKEN = os.environ["TOKEN"]

intents = discord.Intents.all()
bot = discord.Bot(intents=intents)

with open("prompts.json") as f:
	prompts_list = json.load(f)
with open("lyrics.json") as f:
	lyrics = json.load(f)

@bot.event
async def on_ready():
	await bot.change_presence(status=discord.Status.idle, activity=discord.Game("dating sim"))
	print("ready")

@bot.event
async def on_application_command_error(ctx: ApplicationContext, exception):
	await ctx.respond(exception)
# # 	# with open(f"settings/{ctx.guild_id}.json") as f:
# 	# 	settings = json.load(f)
# 	# await ctx.respond(exception, delete_after=settings["Miscellaneous"]["DeleteErrorMessages"])

@bot.event
async def on_message(msg):
	if msg.author.bot or msg.author.id == 511998974069047296:
		return

	content = msg.content.lower()

	for item in prompts_list:
		if any(prompt in content for prompt in item.get("prompts")):
			response = item.get("response")

			if response == "random":
				response = random.choice(lyrics)

			await msg.channel.send(response)
			break

@bot.slash_command()
async def daddy(ctx):
	params = {
		"key": os.environ["SEARCH_ENGINE_API"],
		"cx": os.environ["SEARCH_ENGINE_ID"],
		"q": "Thom Yorke",
		"searchType": "image",
		"start": random.randint(1,100)
	}

	async with ClientSession() as session:
		async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as response:
			data = await response.json()

	await ctx.respond(f"{random.choice(data['items'])['link']}")

@bot.slash_command()
async def ask(ctx: discord.ApplicationContext, message: discord.Option()):
	await ctx.defer()

	messages = [
		{"role": "system", "content": "Pretend you are Thom Yorke"},
		{"role": "user", "content": message}
	]

	resp = openai.ChatCompletion.create(
		model="gpt-3.5-turbo",
		messages=messages
	)
	
	await ctx.respond(resp.choices[0].message.content)

if __name__ == "__main__":
	for file in os.listdir("cogs"):
		if file.endswith(".py"):
			bot.load_extension(f"cogs.{file[:-3]}")
	
	bot.run(TOKEN)