import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os

LOCAL_EVENTS_FILE = "events.json"
REMOTE_EVENTS_URL = "https://raw.githubusercontent.com/Kunakh03/Palia-Clock/main/events.json"


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = self.load_local_events()
        self.update_events.start()

    # -----------------------------
    # Lettura file locale
    # -----------------------------
    def load_local_events(self):
        try:
            with open(LOCAL_EVENTS_FILE, "r", encoding="utf-8") as f:
                print("Eventi caricati dal file locale.")
                return json.load(f)
        except Exception as e:
            print(f"Errore caricamento locale: {e}")
            return {}

    # -----------------------------
    # Fetch remoto con fix MIME
    # -----------------------------
    async def fetch_remote_events(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(REMOTE_EVENTS_URL) as resp:
                if resp.status != 200:
                    print(f"Errore JSON remoto: {resp.status}")
                    return None

                # FIX: GitHub RAW usa text/plain → forziamo la lettura JSON
                data = await resp.json(content_type=None)
                return data

    # -----------------------------
    # Task periodico aggiornamento
    # -----------------------------
    @tasks.loop(minutes=10)
    async def update_events(self):
        remote = await self.fetch_remote_events()
        if remote is None:
            return

        if remote != self.events:
            self.events = remote
            print("Eventi aggiornati dal JSON remoto.")

            # Aggiorna anche il file locale
            try:
                with open(LOCAL_EVENTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.events, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Errore salvataggio locale: {e}")

    @update_events.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Events(bot))
    
