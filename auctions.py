import asyncio
import amulet_nbt
from aiohttp import ClientSession
from base64 import b64decode
from collections import defaultdict
from multiprocessing import Pool, Process

URL = "https://api.hypixel.net/skyblock/auctions?page={}"

async def get_page(session, page_num):
    url = URL.format(page_num)

    async with session.get(url) as resp:
        data = await resp.json()
        return data

def process_page(page):
    def decode(item_bytes):
        decoded = b64decode(item_bytes)
        data = amulet_nbt.load(decoded)
        return data.tag["i"][0]

    def process(v):
        if isinstance(v, amulet_nbt.CompoundTag):
            return {nk: process(nv) for nk, nv in v.items()}
        elif isinstance(v, amulet_nbt.ListTag):
            return [process(nv) for nv in v]
        elif isinstance(v, amulet_nbt.ByteArrayTag):
            return str(v)
        else:
            return v.py_data
    
    auctions = defaultdict(list)
    for auction in page:
        if not auction["bin"]: continue

        decoded = decode(auction["item_bytes"])
        extras = decoded["tag"]["ExtraAttributes"]
        item_id = extras["id"].py_data
        
        data = {k: auction.get(k) for k in ["uuid", "item_name", "tier", "starting_bid"]}
        item_data = {k: process(v) for k,v in extras.items() if not k in ["id", "timestamp"]}

        data["item_data"] = item_data
        auctions[item_id].append(data)

    return auctions

def merge(list_dicts):
    auctions = defaultdict(list)
    for d in list_dicts:
        for k, v in d.items():
            auctions[k].extend(v)
    return auctions

async def gather(session):
    first_page = await get_page(session, 0)
    total_pages = first_page["totalPages"]

    tasks = [asyncio.create_task(get_page(session, page_num)) for page_num in range(1, total_pages)]
    results = await asyncio.gather(*tasks) + [first_page]
    pages = [page["auctions"] for page in results]

    with Pool() as pool:
        results = pool.map(process_page, pages)
    return merge(results)

async def update_loop(dict):
    async with ClientSession() as session:
        while True:            
            new_data = await gather(session)
            dict.clear()
            dict.update(new_data)

def run(dict):
    asyncio.run(update_loop(dict))

def start(dict):
    process = Process(target=run, args=[dict])
    process.start()