import discord
from discord.ext import commands, tasks
from discord import app_commands
from zoneinfo import ZoneInfo
import json
import aiohttp
from datetime import datetime, timedelta
import os
import asyncio

REMOTE_EVENTS_URL = "https://raw.githubusercontent.com/Kunakh03/Palia-Clock/main/static_events.json"
LOCAL_EVENTS_FILE = "static_events.json"
STATE_FILE = "events_state.json"

ANNOUNCE_CHANNEL_ID = 1416482590596141248
MENTION_ROLE_ID = 1393698659421655196

OWNER_ID = 276164839997702147
MAJI_WIKI_URL = "https://palia.wiki.gg/wiki/Maji_Market"

EMOJI_MAJI_START = "<:Dragon:1499063330256457728>"
EMOJI_MAJI_END = "<:Phoenix:1499063237860266076>"

EMOJI_WINTER_START = "<:GhirlandaArgento:1499887346253037778>"
EMOJI_WINTER_END = "<:GhirlandaOro:1499887262404706546>"


# ---------------------------------------------------
# EMBED
# ---------------------------------------------------

def get_event_emojis(event_name: str, event: dict):
    if event_name == "Mercato Maji":
        return EMOJI_MAJI_START, EMOJI_MAJI_END
    if event_name == "Festival delle Luci d’Inverno":
        return EMOJI_WINTER_START, EMOJI_WINTER_END
    return event.get("emoji", ""), event.get("emoji_end", "")


def build_static_start_embed(event: dict, start_ts: int, start_rome: datetime, recovered: bool = False):
    emoji_start, emoji_end = get_event_emojis(event["name"], event)

    embed = discord.Embed(
        title=f"{emoji_start} {event['name']} {emoji_end}".strip(),
        description="",
        color=int(event.get("color", "0x5865F2").replace("#", "0x"), 16)
    )

    ora = start_rome.strftime("%H:%M")

    embed.add_field(name="\u200b", value=f"<@&{MENTION_ROLE_ID}>", inline=False)
    embed.add_field(
        name="\u200b",
        value=f"L'evento inizierà domani alle {ora}!\n**Countdown:** <t:{start_ts}:R>",
        inline=False
    )

    footer = "Evento statico — Recuperato" if recovered else "Evento statico"
    embed.set_footer(text=footer)
    return embed


def build_static_end_embed(event: dict, end_ts: int, end_rome: datetime, recovered: bool = False):
    emoji_start, emoji_end = get_event_emojis(event["name"], event)

    embed = discord.Embed(
        title=f"{emoji_start} {event['name']} {emoji_end}".strip(),
        description="",
        color=int(event.get("color", "0x5865F2").replace("#", "0x"), 16)
    )

    ora = end_rome.strftime("%H:%M")

    embed.add_field(name="\u200b", value=f"<@&{MENTION_ROLE_ID}>", inline=False)
    embed.add_field(
        name="\u200b",
        value=f"L'evento terminerà domani alle {ora}!\n**Countdown:** <t:{end_ts}:R>",
        inline=False
    )

    footer = "Evento statico — Recuperato" if recovered else "Evento statico"
    embed.set_footer(text=footer)
    return embed


# ---------------------------------------------------
# COG
# ---------------------------------------------------

class StaticEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.state = {}
        self.load_local_events()
        self.load_state()
        self._wiki_last_check_day = None

    # ---------------------------
    # CARICAMENTO
    # ---------------------------

    def load_local_events(self):
        try:
            with open(LOCAL_EVENTS_FILE, "r", encoding="utf-8") as f:
                self.events = json.load(f)
        except Exception:
            self.events = []

    async def fetch_remote_events(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(REMOTE_EVENTS_URL) as resp:
                    if resp.status != 200:
                        return None
                    return json.loads(await resp.text())
        except:
            return None

    @tasks.loop(hours=12)
    async def refresh_events(self):
        remote = await self.fetch_remote_events()
        if remote:
            self.events = remote

    # ---------------------------
    # STATO
    # ---------------------------

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except:
                self.state = {}
        else:
            self.state = {}

        if "static" not in self.state:
            self.state["static"] = {}

    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    # ---------------------------
    # CHECK EVENTI
    # ---------------------------

    @tasks.loop(minutes=1)
    async def check_events(self):
        now_rome = datetime.now(ZoneInfo("Europe/Rome"))

        if now_rome.minute not in (0, 30):
            return

        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel is None:
            return

        static_state = self.state.get("static", {})

        for event in self.events:
            name = event["name"]
            tz = ZoneInfo(event["timezone"])

            try:
                start = datetime.fromisoformat(event["start"]).replace(tzinfo=tz)
                end = datetime.fromisoformat(event["end"]).replace(tzinfo=tz)
            except:
                continue

            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
            end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

            event_key = f"{name}_{event['start']}_{event['end']}"

            if event_key not in static_state:
                static_state[event_key] = {"start": False, "end": False}
                self.save_state()

            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())

            # Annuncio INIZIO
            announce_start_dt = (start_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
            if now_rome >= announce_start_dt and not static_state[event_key]["start"]:
                recovered = now_rome > start_rome
                embed = build_static_start_embed(event, start_ts, start_rome, recovered=recovered)
                await channel.send(embed=embed)
                static_state[event_key]["start"] = True
                self.save_state()

            # Annuncio FINE
            announce_end_dt = (end_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
            if now_rome >= announce_end_dt and not static_state[event_key]["end"]:
                recovered = now_rome > end_rome
                embed = build_static_end_embed(event, end_ts, end_rome, recovered=recovered)
                await channel.send(embed=embed)
                static_state[event_key]["end"] = True
                self.save_state()

    # ---------------------------
    # SETUP
    # ---------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        remote = await self.fetch_remote_events()
        if remote:
            self.events = remote

        if not self.check_events.is_running():
            self.check_events.start()
        if not self.refresh_events.is_running():
            self.refresh_events.start()


async def setup(bot):
    await bot.add_cog(StaticEvents(bot))
