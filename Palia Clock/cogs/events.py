import discord
from discord.ext import commands, tasks
from zoneinfo import ZoneInfo
import json
import aiohttp
from datetime import datetime

REMOTE_EVENTS_URL = "https://raw.githubusercontent.com/Claudio/Palia-Clock/main/events.json"
LOCAL_EVENTS_FILE = "events.json"

ANNOUNCE_CHANNEL_ID = 1483229095738212533  # tuo canale 📢-⫶-annunci-ed-eventi


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.state = {}
        self.load_local_events()
        self.load_state()

    # ---------------------------
    # CARICAMENTO EVENTI
    # ---------------------------

    def load_local_events(self):
        try:
            with open(LOCAL_EVENTS_FILE, "r", encoding="utf-8") as f:
                self.events = json.load(f)
            print("Eventi caricati dal file locale.")
        except Exception as e:
            print(f"Errore caricamento eventi locali: {e}")

    async def fetch_remote_events(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(REMOTE_EVENTS_URL) as resp:
                    if resp.status != 200:
                        print(f"Errore JSON remoto: {resp.status}")
                        return None
                    data = await resp.json()
                    return data
        except Exception as e:
            print(f"Errore fetch remoto: {e}")
            return None

    @tasks.loop(hours=12)
    async def refresh_events(self):
        remote = await self.fetch_remote_events()
        if remote:
            self.events = remote
            print("Eventi aggiornati dal JSON remoto.")

    # ---------------------------
    # STATO ANNUNCI
    # ---------------------------

    def load_state(self):
        try:
            with open("events_state.json", "r", encoding="utf-8") as f:
                self.state = json.load(f)
        except:
            self.state = {}

    def save_state(self):
        with open("events_state.json", "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    # ---------------------------
    # CHECK EVENTI
    # ---------------------------

    @tasks.loop(minutes=1)
    async def check_events(self):
        now_rome = datetime.now(ZoneInfo("Europe/Rome"))
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel is None:
            print("Canale annunci non trovato.")
            return

        for event in self.events:
            name = event["name"]
            emoji = event["emoji"]
            tz = ZoneInfo(event["timezone"])

            start = datetime.fromisoformat(event["start"]).replace(tzinfo=tz)
            end = datetime.fromisoformat(event["end"]).replace(tzinfo=tz)

            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
            end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

            # IGNORA EVENTI PASSATI
            if now_rome > end_rome:
                continue

            # Inizializza stato evento
            if name not in self.state:
                self.state[name] = {"start": False, "end": False}

            # Annuncio 1h prima dell'inizio
            if event["announce_1h_before_start"]:
                if not self.state[name]["start"] and now_rome >= start_rome.replace(hour=start_rome.hour - 1):
                    embed = discord.Embed(
                        title=f"{emoji} {name}",
                        description=f"L'evento **{name}** inizierà tra 1 ora!",
                        color=0x9b59b6
                    )
                    await channel.send(embed=embed)
                    self.state[name]["start"] = True
                    self.save_state()

            # Annuncio 1h prima della fine
            if event["announce_1h_before_end"]:
                if not self.state[name]["end"] and now_rome >= end_rome.replace(hour=end_rome.hour - 1):
                    embed = discord.Embed(
                        title=f"{emoji} {name}",
                        description=f"L'evento **{name}** terminerà tra 1 ora!",
                        color=0xe67e22
                    )
                    await channel.send(embed=embed)
                    self.state[name]["end"] = True
                    self.save_state()

    # ---------------------------
    # SETUP
    # ---------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_events.is_running():
            self.check_events.start()
        if not self.refresh_events.is_running():
            self.refresh_events.start()


async def setup(bot):
    await bot.add_cog(Events(bot))
