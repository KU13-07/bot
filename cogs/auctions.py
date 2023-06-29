import discord
import asyncio
import aiohttp
import base64
import amulet_nbt
import json
from discord.ext import tasks

from time import perf_counter

class Auctions(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auctions = {}

        self.update.start()
    
    async def get_page(self, session, page_num):
        url = f"https://api.hypixel.net/skyblock/auctions?page={page_num}"
        async with session.get(url) as response:
            data = await response.json()
            return data        
    
    def process_auctions(self, page):
        def decode(item_bytes):
            decoded = base64.b64decode(item_bytes)
            data = amulet_nbt.load(decoded)

            return data.tag["i"][0]
        
        processed_auctions = {}
        for auction in page["auctions"]:
            nbt_data = decode(auction["item_bytes"])
            extras = nbt_data["tag"]["ExtraAttributes"]

            if extras["id"].py_data == "POTION":
                continue

            relevant_keys = ["item_name", "tier", "starting_bid", "bin"]
            data = {key: auction[key] for key in relevant_keys}
            data["Count"] = nbt_data["Count"].py_data
            data["data"] = {}

            processing_logic = {
                "petInfo": lambda value: {
                    key: json.loads(value.py_data).get(key)
                    for key in ["type", "exp", "tier", "heldItem", "candyUsed"]
                },
                "enchantments": lambda value: {enchant: level.py_data for enchant, level in value.items()},
                "gems": lambda value: {
                    gem: [slot.py_data for slot in data.py_data]
                    if gem == "unlocked_slots"
                    else (data["quality"] if isinstance(data, amulet_nbt.CompoundTag) else data).py_data
                    for gem, data in value.items()
                },
                "runes": lambda value: {rune: level.py_data for rune, level in value.items()},
                "attributes": lambda value: {k: v.py_data for k, v in value.items()},
                "necromancer_souls": lambda value: [{k: v.py_data for k, v in mob.items()} for mob in value],
            }

            for key, value in extras.items():
                if key in ["uuid", "timestamp", "originTag", "spawnedFor", "bossId", "dungeon_skill_req", "baseStatBoostPercentage", "item_durability"]:
                    continue

                if key in processing_logic:
                    data["data"][key] = processing_logic[key](value)
                elif isinstance(value, amulet_nbt.ListTag):
                    data["data"][key] = [scroll.py_data for scroll in value]
                elif isinstance(value, amulet_nbt.ByteArrayTag):
                    data["data"][key] = str(value.py_data)
                else:
                    data["data"][key] = value.py_data

            processed_auctions[auction["uuid"]] = data
        return processed_auctions

    @tasks.loop()#seconds=30)
    async def update(self):
        start = perf_counter()
        async with aiohttp.ClientSession() as session:
            first_page = await self.get_page(session, 0)
            total_pages = first_page["totalPages"]

            tasks = [asyncio.ensure_future(self.get_page(session, page_num)) for page_num in range(1, total_pages)]
            pages = await asyncio.gather(*tasks) + [first_page]
        
        tasks = [asyncio.to_thread(self.process_auctions, page) for page in pages]
        results = await asyncio.gather(*tasks)
        self.auctions = {k:v for page in results for k, v in page.items()}

        print(f"Total auctions: {len(self.auctions)}")
        print(f"Time taken: {perf_counter() - start:.2f} seconds")
        
    @discord.slash_command()
    async def save(self, ctx):
        with open("save.json", "w") as f:
            json.dump(self.auctions, f, indent=2)
        await ctx.respond("done")

def setup(bot: discord.Bot):
    bot.add_cog(Auctions(bot))