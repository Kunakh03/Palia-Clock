import discord
from discord.ext import commands, tasks
from discord import app_commands
from zoneinfo import ZoneInfo
import json
import aiohttp
from datetime import datetime, timedelta

REMOTE_EVENTS_URL = "https://raw.githubusercontent.com/Kunakh03/Palia-Clock/main/events.json"
LOCAL_EVENTS_FILE = "events.json"

ANNOUNCE_CHANNEL_ID = 1483229095738212533
MENTION_ROLE_ID = 1393698659421655196

# Emoji personalizzate
EMOJI_MAJI_START = "<:Dragon:1499063330256457728>"
EMOJI_MAJI_END = "<:Phoenix:1499063237860266076>"

EMOJI_WINTER_START = "<:GhirlandaArgento:1499887346253037778>"
EMOJI_WINTER_END = "<:GhirlandaOro:1499887262404706546>"


# ---------------------------------------------------
# EMBED PER EVENTI STATICI
# ---------------------------------------------------

def get_event_emojis(event_name: str, event: dict):
    if event_name == "Mercato Maji":
        return EMOJI_MAJI_START, EMOJI_MAJI_END
    if event_name == "Festival delle Luci d’Inverno":
        return EMOJI_WINTER_START, EMOJI_WINTER_END
    return event.get("emoji", ""), event.get("emoji_end", "")


def build_static_start_embed(event: dict, start_ts: int, start_rome: datetime):
    emoji_start, emoji_end = get_event_emojis(event["name"], event)

    embed = discord.Embed(
        title=f"{emoji_start} {event['name']} {emoji_end}".strip(),
        description="",
        color=int(event.get("color", "0x5865F2").replace("#", "0x"), 16)
    )

    ora = start_rome.strftime("%H:%M")

    embed.add_field(name="", value=f"<@&{MENTION_ROLE_ID}>", inline=False)

    embed.add_field(
        name="",
        value=f"L'evento inizierà domani alle {ora}!\n**Countdown:** <t:{start_ts}:R>",
        inline=False
    )

    embed.set_footer(text="Evento statico")
    return embed


def build_static_end_embed(event: dict, end_ts: int, end_rome: datetime):
    emoji_start, emoji_end = get_event_emojis(event["name"], event)

    embed = discord.Embed(
        title=f"{emoji_start} {event['name']} {emoji_end}".strip(),
        description="",
        color=int(event.get("color", "0x5865F2").replace("#", "0x"), 16)
    )

    ora = end_rome.strftime("%H:%M")

    embed.add_field(name="", value=f"<@&{MENTION_ROLE_ID}>", inline=False)

    embed.add_field(
        name="",
        value=f"L'evento terminerà domani alle {ora}!\n**Countdown:** <t:{end_ts}:R>",
        inline=False
    )

    embed.set_footer(text="Evento statico")
    return embed


# ---------------------------------------------------
# COG EVENTI STATICI
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

                    text = await resp.text()
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        print("Errore: JSON remoto non valido.")
                        return None

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
    # RESET AUTOMATICO EVENTI FINITI
    # ---------------------------

    def reset_if_finished(self, event_name: str, now_rome: datetime):
        future_events = [
            e for e in self.events
            if e["name"] == event_name and
            datetime.fromisoformat(e["end"]).replace(
                tzinfo=ZoneInfo(e["timezone"])
            ).astimezone(ZoneInfo("Europe/Rome")) > now_rome
        ]

        if future_events:
            self.state[event_name] = {"start": False, "end": False}
        else:
            if event_name in self.state:
                del self.state[event_name]

        self.save_state()

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

            try:
                start = datetime.fromisoformat(event["start"]).replace(tzinfo=tz)
                end = datetime.fromisoformat(event["end"]).replace(tzinfo=tz)
            except Exception:
                print(f"Evento '{name}' ha una data non valida. Saltato.")
                continue

            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
            end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

            if now_rome > end_rome:
                self.reset_if_finished(name, now_rome)
                continue

            if name not in self.state:
                self.state[name] = {"start": False, "end": False}

            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())

            announce_start_dt = (start_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
            if not self.state[name]["start"] and now_rome >= announce_start_dt:
                embed = build_static_start_embed(event, start_ts, start_rome)
                await channel.send(embed=embed)
                self.state[name]["start"] = True
                self.save_state()

            announce_end_dt = (end_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
            if not self.state[name]["end"] and now_rome >= announce_end_dt:
                embed = build_static_end_embed(event, end_ts, end_rome)
                await channel.send(embed=embed)
                self.state[name]["end"] = True
                self.save_state()

    # ---------------------------
    # COMANDO /testevents
    # ---------------------------

    @app_commands.command(name="testevents", description="Testa un evento statico (inizio o fine).")
    @app_commands.describe(evento="Seleziona l'evento", tipo="Inizio o fine")
    async def testevents(self, interaction: discord.Interaction, evento: str, tipo: str):

        selected = [e for e in self.events if e["name"] == evento]
        if not selected:
            return await interaction.response.send_message("Evento non trovato.", ephemeral=True)

        event = selected[0]

        tz = ZoneInfo(event["timezone"])
        start = datetime.fromisoformat(event["start"]).replace(tzinfo=tz)
        end = datetime.fromisoformat(event["end"]).replace(tzinfo=tz)

        start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
        end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())

        if tipo == "inizio":
            embed = build_static_start_embed(event, start_ts, start_rome)
        else:
            embed = build_static_end_embed(event, end_ts, end_rome)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------------------------
    # AUTOCOMPLETE
    # ---------------------------

    @testevents.autocomplete("evento")
    async def evento_autocomplete(self, interaction: discord.Interaction, current: str):
        ordered = sorted(self.events, key=lambda e: e["start"])

        seen = set()
        unique = []
        for e in ordered:
            if e["name"] not in seen:
                seen.add(e["name"])
                unique.append(e["name"])

        return [
            app_commands.Choice(name=name, value=name)
            for name in unique
            if current.lower() in name.lower()
        ]

    @testevents.autocomplete("tipo")
    async def tipo_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["inizio", "fine"]
        return [
            app_commands.Choice(name=o, value=o)
            for o in options
            if current.lower() in o.lower()
        ]

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
