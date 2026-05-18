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

ANNOUNCE_CHANNEL_ID = 1483229095738212533
MENTION_ROLE_ID = 1393698659421655196

# Utente a cui mandare il DM in caso di cambiamenti sulla wiki
OWNER_ID = 276164839997702147

# Wiki Maji Market
MAJI_WIKI_URL = "https://palia.wiki.gg/wiki/Maji_Market"

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


def build_static_start_embed(event: dict, start_ts: int, start_rome: datetime, recovered: bool = False):
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

    embed.add_field(name="", value=f"<@&{MENTION_ROLE_ID}>", inline=False)
    embed.add_field(
        name="",
        value=f"L'evento terminerà domani alle {ora}!\n**Countdown:** <t:{end_ts}:R>",
        inline=False
    )

    footer = "Evento statico — Recuperato" if recovered else "Evento statico"
    embed.set_footer(text=footer)
    return embed


# ---------------------------------------------------
# COG EVENTI STATICI
# ---------------------------------------------------

class StaticEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.state = {}
        self.load_local_events()
        self.load_state()
        self._wiki_last_check_day = None  # per evitare doppi check la stessa domenica

    # ---------------------------
    # CARICAMENTO EVENTI
    # ---------------------------

    def load_local_events(self):
        try:
            with open(LOCAL_EVENTS_FILE, "r", encoding="utf-8") as f:
                self.events = json.load(f)
            print("[StaticEvents] Eventi caricati dal file locale.")
        except Exception as e:
            print(f("[StaticEvents] Errore caricamento eventi locali: {e}"))
            self.events = []

    async def fetch_remote_events(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(REMOTE_EVENTS_URL) as resp:
                    if resp.status != 200:
                        print(f"[StaticEvents] Errore JSON remoto: {resp.status}")
                        return None

                    text = await resp.text()
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        print("[StaticEvents] Errore: JSON remoto non valido.")
                        return None

        except Exception as e:
            print(f"[StaticEvents] Errore fetch remoto: {e}")
            return None

    @tasks.loop(hours=12)
    async def refresh_events(self):
        remote = await self.fetch_remote_events()
        if remote:
            self.events = remote
            print("[StaticEvents] Eventi aggiornati dal JSON remoto.")

    # ---------------------------
    # STATO ANNUNCI
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
    # RESET AUTOMATICO EVENTI FINITI
    # ---------------------------

    def reset_if_finished(self, event_name: str, now_rome: datetime):
        static_state = self.state.get("static", {})

        future_events = [
            e for e in self.events
            if e["name"] == event_name and
            datetime.fromisoformat(e["end"]).replace(
                tzinfo=ZoneInfo(e["timezone"])
            ).astimezone(ZoneInfo("Europe/Rome")) > now_rome
        ]

        if future_events:
            static_state[event_name] = {"start": False, "end": False}
        else:
            if event_name in static_state:
                del static_state[event_name]

        self.state["static"] = static_state
        self.save_state()

    # ---------------------------
    # CHECK EVENTI
    # ---------------------------

    @tasks.loop(minutes=1)
    async def check_events(self):
        now_rome = datetime.now(ZoneInfo("Europe/Rome"))
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel is None:
            print("[StaticEvents] Canale annunci non trovato.")
            return

        static_state = self.state.get("static", {})

        for event in self.events:
            name = event["name"]
            tz = ZoneInfo(event["timezone"])

            try:
                start = datetime.fromisoformat(event["start"]).replace(tzinfo=tz)
                end = datetime.fromisoformat(event["end"]).replace(tzinfo=tz)
            except Exception:
                print(f"[StaticEvents] Evento '{name}' ha una data non valida. Saltato.")
                continue

            start_rome = start.astimezone(ZoneInfo("Europe/Rome"))
            end_rome = end.astimezone(ZoneInfo("Europe/Rome"))

            if now_rome > end_rome:
                self.reset_if_finished(name, now_rome)
                continue

            if name not in static_state:
                static_state[name] = {"start": False, "end": False}
                self.save_state()

            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())

            # Annuncio INIZIO — RECUPERO AUTOMATICO
            announce_start_dt = (start_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
            if now_rome >= announce_start_dt and not static_state[name]["start"]:
                recovered = now_rome > start_rome
                embed = build_static_start_embed(event, start_ts, start_rome, recovered=recovered)
                await channel.send(embed=embed)
                static_state[name]["start"] = True
                self.save_state()

            # Annuncio FINE — RECUPERO AUTOMATICO
            announce_end_dt = (end_rome - timedelta(days=1)).replace(hour=18, minute=0, second=0)
            if now_rome >= announce_end_dt and not static_state[name]["end"]:
                recovered = now_rome > end_rome
                embed = build_static_end_embed(event, end_ts, end_rome, recovered=recovered)
                await channel.send(embed=embed)
                static_state[name]["end"] = True
                self.save_state()

    # ---------------------------
    # CONTROLLO WIKI DOMENICA 19:00
    # ---------------------------

    async def fetch_maji_wiki_html(self) -> str | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(MAJI_WIKI_URL) as resp:
                    if resp.status != 200:
                        print(f"[StaticEvents] Errore fetch wiki Maji: {resp.status}")
                        return None
                    return await resp.text()
        except Exception as e:
            print(f"[StaticEvents] Errore fetch wiki Maji: {e}")
            return None

    def parse_maji_future_dates(self, html: str):
        """
        Parser semplice: cerca la sezione 'Future Dates' e prende le righe
        con due date (start/end) in formato 'Month DD, YYYY – Month DD, YYYY'.
        Questo è volutamente minimale: se la wiki cambia struttura,
        andrà eventualmente adattato.
        """
        future = []

        marker = "Future Dates"
        idx = html.find(marker)
        if idx == -1:
            return future

        snippet = html[idx: idx + 8000]  # porzione dopo 'Future Dates'

        import re
        # pattern molto semplice: "Month DD, YYYY" – "Month DD, YYYY"
        date_pattern = r"([A-Z][a-z]+ \d{1,2}, \d{4})\s*[\u2013\-]\s*([A-Z][a-z]+ \d{1,2}, \d{4})"
        matches = re.findall(date_pattern, snippet)

        from datetime import datetime as dt

        for start_str, end_str in matches:
            try:
                start_dt = dt.strptime(start_str, "%B %d, %Y")
                end_dt = dt.strptime(end_str, "%B %d, %Y")
            except ValueError:
                continue

            # convertiamo in ISO con orario 00:00:00 in America/Los_Angeles
            start_iso = start_dt.strftime("%Y-%m-%dT00:00:00")
            end_iso = end_dt.strftime("%Y-%m-%dT00:00:00")

            future.append({
                "start": start_iso,
                "end": end_iso,
            })

        return future

    def extract_maji_from_events(self):
        maji = []
        for e in self.events:
            if e.get("name") == "Mercato Maji":
                maji.append({
                    "start": e.get("start"),
                    "end": e.get("end"),
                })
        # ordiniamo per start
        maji.sort(key=lambda x: x["start"])
        return maji

    def compare_maji_dates(self, wiki_dates, json_dates) -> bool:
        """
        Ritorna True se ci sono differenze tra wiki e JSON remoto.
        Confronto semplice su lista di (start, end) ordinata.
        """
        if len(wiki_dates) != len(json_dates):
            return True

        for w, j in zip(wiki_dates, json_dates):
            if w["start"] != j["start"] or w["end"] != j["end"]:
                return True

        return False

    @tasks.loop(hours=24)
    async def check_maji_wiki(self):
        """
        Controllo giornaliero, ma agisce solo la domenica alle 19:00 Europe/Rome.
        Se le date del Maji sulla wiki differiscono dal JSON remoto,
        manda un DM all'OWNER_ID.
        """
        now_rome = datetime.now(ZoneInfo("Europe/Rome"))
        # Domenica = 6
        if now_rome.weekday() != 6:
            return

        if now_rome.hour != 19:
            return

        # Evita doppi check la stessa domenica
        day_key = now_rome.strftime("%Y-%m-%d")
        if self._wiki_last_check_day == day_key:
            return

        self._wiki_last_check_day = day_key

        print("[StaticEvents] Controllo wiki Maji Market...")

        html = await self.fetch_maji_wiki_html()
        if not html:
            return

        wiki_dates = self.parse_maji_future_dates(html)
        if not wiki_dates:
            print("[StaticEvents] Nessuna data futura trovata sulla wiki (parser).")
            return

        # Usa gli eventi attualmente caricati (che derivano dal JSON remoto)
        json_maji = self.extract_maji_from_events()

        changed = self.compare_maji_dates(wiki_dates, json_maji)
        if not changed:
            print("[StaticEvents] Le date del Maji sulla wiki coincidono con il JSON remoto.")
            return

        # Se ci sono differenze, manda DM
        try:
            user = await self.bot.fetch_user(OWNER_ID)
            msg_lines = ["Le date del **Mercato Maji** sulla wiki sono cambiate rispetto al JSON remoto.", ""]
            msg_lines.append("**Wiki (Future Dates):**")
            for d in wiki_dates:
                msg_lines.append(f"- {d['start']} → {d['end']}")

            msg_lines.append("")
            msg_lines.append("**JSON remoto (Mercato Maji):**")
            for d in json_maji:
                msg_lines.append(f"- {d['start']} → {d['end']}")

            await user.send("\n".join(msg_lines))
            print("[StaticEvents] DM inviato per cambiamento date Maji.")
        except Exception as e:
            print(f"[StaticEvents] Errore invio DM Maji: {e}")

    @check_maji_wiki.before_loop
    async def before_check_maji_wiki(self):
        # Aspetta che il bot sia pronto
        await self.bot.wait_until_ready()
        # Nessun allineamento speciale: il loop gira ogni 24h,
        # ma la logica interna filtra per domenica 19:00.

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
    # COMANDO /debugevents
    # ---------------------------

    @app_commands.command(name="debugevents", description="Mostra gli eventi statici caricati e lo stato annunci.")
    async def debugevents(self, interaction: discord.Interaction):
        static_state = self.state.get("static", {})
        lines = []

        lines.append("**Eventi caricati:**")
        for e in sorted(self.events, key=lambda x: x.get("start", "")):
            name = e.get("name", "??")
            start = e.get("start", "?")
            end = e.get("end", "?")
            lines.append(f"- `{name}`: {start} → {end}")

        lines.append("")
        lines.append("**Stato annunci (static):**")
        if not static_state:
            lines.append("_Nessuno stato salvato._")
        else:
            for name, st in static_state.items():
                lines.append(f"- `{name}`: start={st.get('start')}, end={st.get('end')}")

        msg = "\n".join(lines)
        await interaction.response.send_message(msg, ephemeral=True)

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
        # Carica subito gli eventi remoti all'avvio
        remote = await self.fetch_remote_events()
        if remote:
            self.events = remote
            print("[StaticEvents] Eventi caricati dal JSON remoto all'avvio.")

        if not self.check_events.is_running():
            self.check_events.start()
        if not self.refresh_events.is_running():
            self.refresh_events.start()
        if not self.check_maji_wiki.is_running():
            self.check_maji_wiki.start()


async def setup(bot):
    await bot.add_cog(StaticEvents(bot))
