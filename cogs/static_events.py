import discord
from discord.ext import commands, tasks
from discord import app_commands
from zoneinfo import ZoneInfo
import json
import aiohttp
from datetime import datetime, timedelta
import os

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
# EMBED REALI (ANNUNCI)
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
    now_rome = datetime.now(ZoneInfo("Europe/Rome"))

    embed.add_field(name="\u200b", value=f"<@&{MENTION_ROLE_ID}>", inline=False)
    embed.add_field(
        name="\u200b",
        value=(
            f"L'evento inizierà domani alle {ora}!\n"
            f"**Countdown:** {'00:00' if now_rome >= start_rome else f'<t:{start_ts}:R>'}"
        ),
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
    now_rome = datetime.now(ZoneInfo("Europe/Rome"))

    embed.add_field(name="\u200b", value=f"<@&{MENTION_ROLE_ID}>", inline=False)
    embed.add_field(
        name="\u200b",
        value=(
            f"L'evento terminerà domani alle {ora}!\n"
            f"**Countdown:** {'00:00' if now_rome >= end_rome else f'<t:{end_ts}:R>'}"
        ),
        inline=False
    )

    footer = "Evento statico — Recuperato" if recovered else "Evento statico"
    embed.set_footer(text=footer)
    return embed


# ---------------------------------------------------
# EMBED TEST (PER /testevents)
# ---------------------------------------------------

def build_test_start_embed(event: dict, start_rome: datetime):
    emoji_start, emoji_end = get_event_emojis(event["name"], event)

    embed = discord.Embed(
        title=f"[TEST] {emoji_start} {event['name']} {emoji_end}".strip(),
        description="",
        color=int(event.get("color", "0x5865F2").replace("#", "0x"), 16)
    )

    ora = start_rome.strftime("%H:%M")
    embed.add_field(
        name="\u200b",
        value=f"L'evento inizierà alle {ora} (TEST).",
        inline=False
    )
    embed.set_footer(text="Evento statico — TEST")
    return embed


def build_test_end_embed(event: dict, end_rome: datetime):
    emoji_start, emoji_end = get_event_emojis(event["name"], event)

    embed = discord.Embed(
        title=f"[TEST] {emoji_start} {event['name']} {emoji_end}".strip(),
        description="",
        color=int(event.get("color", "0x5865F2").replace("#", "0x"), 16)
    )

    ora = end_rome.strftime("%H:%M")
    embed.add_field(
        name="\u200b",
        value=f"L'evento terminerà alle {ora} (TEST).",
        inline=False
    )
    embed.set_footer(text="Evento statico — TEST")
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
        except Exception:
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
    # CHECK EVENTI
    # ---------------------------

    @tasks.loop(minutes=1)
    async def check_events(self):
        now_rome = datetime.now(ZoneInfo("Europe/Rome"))

        # Allinea a :00 e :30
        if now_rome.minute not in (0, 30):
            return

        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel is None:
            return

        static_state = self.state.get("static", {})

        # 1) Costruisci lista eventi validi (non finiti)
        valid_events = []
        for e in self.events:
            try:
                tz = ZoneInfo(e["timezone"])
                start = datetime.fromisoformat(e["start"]).replace(tzinfo=tz)
                end = datetime.fromisoformat(e["end"]).replace(tzinfo=tz)
            except Exception:
                continue

            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
            end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

            # Ignora eventi già finiti
            if end_rome < now_rome:
                continue

            valid_events.append((e, start_rome, end_rome))

        if not valid_events:
            return

        # 2) Prendi SOLO l’evento più vicino nel tempo
        event, start_rome, end_rome = sorted(valid_events, key=lambda x: x[1])[0]

        name = event["name"]
        event_key = f"{name}_{event['start']}_{event['end']}"

        if event_key not in static_state:
            static_state[event_key] = {"start": False, "end": False}
            self.save_state()

        start_ts = int(start_rome.timestamp())
        end_ts = int(end_rome.timestamp())

        # ANNUNCIO INIZIO
        announce_start_dt = (start_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
        if now_rome >= announce_start_dt and not static_state[event_key]["start"]:
            recovered = now_rome > start_rome
            embed = build_static_start_embed(event, start_ts, start_rome, recovered=recovered)
            await channel.send(embed=embed)
            static_state[event_key]["start"] = True
            self.save_state()

        # ANNUNCIO FINE
        announce_end_dt = (end_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
        if now_rome >= announce_end_dt and not static_state[event_key]["end"]:
            recovered = now_rome > end_rome
            embed = build_static_end_embed(event, end_ts, end_rome, recovered=recovered)
            await channel.send(embed=embed)
            static_state[event_key]["end"] = True
            self.save_state()

    # ---------------------------
    # CONTROLLO SETTIMANALE WIKI (MAJI MARKET)
    # ---------------------------

    @tasks.loop(hours=24)
    async def check_wiki_updates(self):
        now = datetime.now(ZoneInfo("Europe/Rome"))

        # Controlla se è domenica
        if now.weekday() != 6:  # 6 = Domenica
            return

        # Controlla se è passato l'orario del check (19:00)
        if now.hour < 19:
            return

        # Evita doppi check nella stessa domenica
        today_str = now.strftime("%Y-%m-%d")
        if self._wiki_last_check_day == today_str:
            return

        # Scarica pagina Wiki
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(MAJI_WIKI_URL) as resp:
                    if resp.status != 200:
                        return
                    html = await resp.text()
        except:
            return

        # Parsing HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Trova tabella "Future Dates"
        table = soup.find("table", {"class": "wikitable"})
        if not table:
            return

        rows = table.find_all("tr")
        if len(rows) < 2:
            return

        cols = rows[1].find_all("td")
        if len(cols) < 3:
            return

        start_text = cols[1].get_text(strip=True)
        end_text = cols[2].get_text(strip=True)

        # Converte date Wiki
        def parse_date(text):
            try:
                return datetime.strptime(text, "%B %d, %Y")
            except:
                return None

        wiki_start = parse_date(start_text)
        wiki_end = parse_date(end_text)

        if not wiki_start or not wiki_end:
            return

        # Trova il prossimo Maji futuro nel JSON locale
        now_rome = datetime.now(ZoneInfo("Europe/Rome"))
        future_maji = []

        for e in self.events:
            if e["name"] != "Mercato Maji":
                continue

            tz = ZoneInfo(e["timezone"])
            start = datetime.fromisoformat(e["start"]).replace(tzinfo=tz)
            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))

            if start_rome > now_rome:
                future_maji.append(e)

        if not future_maji:
            return

        next_maji = sorted(future_maji, key=lambda x: x["start"])[0]

        local_start = datetime.fromisoformat(next_maji["start"])
        local_end = datetime.fromisoformat(next_maji["end"])

        # Confronto date
        if (local_start.date() != wiki_start.date()) or (local_end.date() != wiki_end.date()):
            user = self.bot.get_user(OWNER_ID)
            if user:
                await user.send(
                    f"⚠️ Le date del Maji Market sulla Wiki sono cambiate!\n\n"
                    f"Vecchie date:\n"
                    f"- Start: {local_start.date()}\n"
                    f"- End: {local_end.date()}\n\n"
                    f"Nuove date:\n"
                    f"- Start: {wiki_start.date()}\n"
                    f"- End: {wiki_end.date()}\n\n"
                    f"Aggiorna il file static_events.json."
                )

        # Segna il check come fatto
        self._wiki_last_check_day = today_str

    # ---------------------------
    # COMANDO /testevents
    # ---------------------------

    @app_commands.command(name="testevents", description="Testa un evento statico (inizio o fine).")
    @app_commands.describe(
        evento="Seleziona l'evento",
        tipo="Scegli se testare l'inizio o la fine"
    )
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

        if tipo == "inizio":
            embed = build_test_start_embed(event, start_rome)
        else:
            embed = build_test_end_embed(event, end_rome)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------------------------
    # COMANDO /debugevents
    # ---------------------------

    @app_commands.command(name="debugevents", description="Mostra info sull'evento statico attuale.")
    async def debugevents(self, interaction: discord.Interaction):
        now_rome = datetime.now(ZoneInfo("Europe/Rome"))
        static_state = self.state.get("static", {})

        # Ricostruisci lista eventi validi (come in check_events)
        valid_events = []
        for e in self.events:
            try:
                tz = ZoneInfo(e["timezone"])
                start = datetime.fromisoformat(e["start"]).replace(tzinfo=tz)
                end = datetime.fromisoformat(e["end"]).replace(tzinfo=tz)
            except Exception:
                continue

            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
            end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

            if end_rome < now_rome:
                continue

            valid_events.append((e, start_rome, end_rome))

        if not valid_events:
            return await interaction.response.send_message(
                "Nessun evento statico valido trovato.", ephemeral=True
            )

        event, start_rome, end_rome = sorted(valid_events, key=lambda x: x[1])[0]
        name = event["name"]
        event_key = f"{name}_{event['start']}_{event['end']}"
        state = static_state.get(event_key, {"start": False, "end": False})

        lines = []
        lines.append("**Evento statico attuale / prossimo:**")
        lines.append(f"- Nome: `{name}`")
        lines.append(f"- Start: `{event['start']}` (Roma: {start_rome})")
        lines.append(f"- End: `{event['end']}` (Roma: {end_rome})")
        lines.append(f"- Chiave stato: `{event_key}`")
        lines.append("")
        lines.append("**Stato annunci:**")
        lines.append(f"- start: `{state.get('start')}`")
        lines.append(f"- end: `{state.get('end')}`")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    # ---------------------------
    # AUTOCOMPLETE
    # ---------------------------

    @testevents.autocomplete("evento")
    async def evento_autocomplete(self, interaction: discord.Interaction, current: str):
        ordered = sorted(self.events, key=lambda e: e.get("start", ""))

        seen = set()
        unique = []
        for e in ordered:
            name = e.get("name", "??")
            if name not in seen:
                seen.add(name)
                unique.append(name)

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
        remote = await self.fetch_remote_events()
        if remote:
            self.events = remote

        if not self.check_events.is_running():
            self.check_events.start()
        if not self.refresh_events.is_running():
            self.refresh_events.start()
        if not self.check_wiki_updates.is_running():
            self.check_wiki_updates.start()

async def setup(bot):
    await bot.add_cog(StaticEvents(bot))
