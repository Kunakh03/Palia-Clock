import discord
from discord.ext import commands, tasks
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
import json
import os

ANNOUNCE_CHANNEL_ID = 1483229095738212533
MENTION_ROLE_ID = 1393698659421655196

LOCAL_EVENTS_FILE = "static_events.json"
STATE_FILE = "events_state.json"


def build_start_embed(event, start_ts, start_rome, recovered=False):
    embed = discord.Embed(
        title=f"{event['name']} — Inizio",
        color=0x5865F2
    )
    embed.add_field(name="", value=f"<@&{MENTION_ROLE_ID}>", inline=False)
    embed.add_field(
        name="",
        value=f"L'evento inizierà domani alle {start_rome.strftime('%H:%M')}!\n"
              f"**Countdown:** <t:{start_ts}:R>",
        inline=False
    )
    embed.set_footer(text="Recuperato" if recovered else "Evento statico")
    return embed


def build_end_embed(event, end_ts, end_rome, recovered=False):
    embed = discord.Embed(
        title=f"{event['name']} — Fine",
        color=0x5865F2
    )
    embed.add_field(name="", value=f"<@&{MENTION_ROLE_ID}>", inline=False)
    embed.add_field(
        name="",
        value=f"L'evento terminerà domani alle {end_rome.strftime('%H:%M')}!\n"
              f"**Countdown:** <t:{end_ts}:R>",
        inline=False
    )
    embed.set_footer(text="Recuperato" if recovered else "Evento statico")
    return embed


class StaticEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.state = {}
        self.load_events()
        self.load_state()

    # ---------------------------
    # CARICAMENTO EVENTI
    # ---------------------------

    def load_events(self):
        try:
            with open(LOCAL_EVENTS_FILE, "r", encoding="utf-8") as f:
                self.events = json.load(f)
        except Exception:
            self.events = []

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}
        else:
            self.state = {}

        if "static" not in self.state:
            self.state["static"] = {}

    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    # ---------------------------
    # LOOP MINIMALE
    # ---------------------------

    @tasks.loop(minutes=1)
    async def check_events(self):
        print("[StaticEvents] Loop attivo — controllo eventi...")

        now_rome = datetime.now(ZoneInfo("Europe/Rome"))
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel is None:
            print("[StaticEvents] Canale non trovato.")
            return

        static_state = self.state["static"]

        for event in self.events:
            try:
                tz = ZoneInfo(event["timezone"])
                start = datetime.fromisoformat(event["start"]).replace(tzinfo=tz)
                end = datetime.fromisoformat(event["end"]).replace(tzinfo=tz)
            except Exception as e:
                print(f"[StaticEvents] Errore parsing evento: {e}")
                continue

            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
            end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

            name = event["name"]

            if name not in static_state:
                static_state[name] = {"start": False, "end": False}
                self.save_state()

            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())

            # Annuncio INIZIO
            announce_start_dt = (start_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
            if now_rome >= announce_start_dt and not static_state[name]["start"]:
                recovered = now_rome > start_rome
                embed = build_start_embed(event, start_ts, start_rome, recovered)
                await channel.send(embed=embed)
                static_state[name]["start"] = True
                self.save_state()
                print(f"[StaticEvents] Annunciato INIZIO per {name}")

            # Annuncio FINE
            announce_end_dt = (end_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
            if now_rome >= announce_end_dt and not static_state[name]["end"]:
                recovered = now_rome > end_rome
                embed = build_end_embed(event, end_ts, end_rome, recovered)
                await channel.send(embed=embed)
                static_state[name]["end"] = True
                self.save_state()
                print(f"[StaticEvents] Annunciato FINE per {name}")

    @commands.Cog.listener()
    async def on_ready(self):
        print("[StaticEvents] COG pronto, avvio loop...")
        if not self.check_events.is_running():
            self.check_events.start()


async def setup(bot):
    await bot.add_cog(StaticEvents(bot))
