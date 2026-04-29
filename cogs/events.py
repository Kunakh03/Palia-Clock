import discord
from discord.ext import commands, tasks
from zoneinfo import ZoneInfo
import json
import aiohttp
from datetime import datetime

REMOTE_EVENTS_URL = "https://raw.githubusercontent.com/Claudio/Palia-Clock/main/events.json"
LOCAL_EVENTS_FILE = "events.json"

ANNOUNCE_CHANNEL_ID = 1483229095738212533  # canale annunci


# ---------------------------------------------------
# EMBED PER EVENTI RICORRENTI
# ---------------------------------------------------

def build_recurring_embed(event: dict, start_ts: int, start_rome: datetime):
    # Titolo con emoji (solo se presenti)
    emoji_start = event.get("emoji", "")
    emoji_end = event.get("emoji_end", "")
    title = f"{emoji_start} {event['name']} {emoji_end}".strip()

    # Testo automatico
    ora = start_rome.strftime("%H:%M")
    description = (
        f"L'evento inizierà domani alle {ora}!\n"
        f"**Countdown:** <t:{start_ts}:R>"
    )

    embed = discord.Embed(
        title=title,
        description=description,
        color=int(event.get("color", "0x5865F2").replace("#", "0x"), 16)
    )

    embed.set_footer(text="Palia Clock • Evento")
    return embed


# ---------------------------------------------------
# COG EVENTI FISSI
# ---------------------------------------------------

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
                    return await resp.json()
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
            tz = ZoneInfo(event["timezone"])

            start = datetime.fromisoformat(event["start"]).replace(tzinfo=tz)
            end = datetime.fromisoformat(event["end"]).replace(tzinfo=tz)

            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
            end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

            # IGNORA EVENTI PASSATI
            if now_rome > end_rome:
                continue

            # Stato evento
            if name not in self.state:
                self.state[name] = {"start": False, "end": False}

            # Timestamp UNIX
            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())

            # Annuncio 1h prima dell'inizio
            if event["announce_1h_before_start"]:
                if not self.state[name]["start"] and now_rome >= (start_rome - timedelta(hours=1)):
                    embed = build_recurring_embed(event, start_ts, start_rome)
                    await channel.send(embed=embed)
                    self.state[name]["start"] = True
                    self.save_state()

            # Annuncio 1h prima della fine
            if event["announce_1h_before_end"]:
                if not self.state[name]["end"] and now_rome >= (end_rome - timedelta(hours=1)):
                    embed = discord.Embed(
                        title=f"{event.get('emoji', '')} {name}",
                        description=f"L'evento terminerà tra 1 ora!",
                        color=0xe67e22
                    )
                    embed.set_footer(text="Palia Clock • Evento")
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
