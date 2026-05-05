import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import os

DYNAMIC_EVENTS_FILE = "dynamic_events.json"
STATE_FILE = "events_state.json"

ANNOUNCE_CHANNEL_ID = 1416482590596141248
MENTION_ROLE_ID = 1393698659421655196  # Ruolo Paliani

# Emoji personalizzate
EMOJI_MAJI_START = "<:Dragon:1499063330256457728>"
EMOJI_MAJI_END = "<:Phoenix:1499063237860266076>"

EMOJI_WINTER_START = "<:GhirlandaArgento:1499887346253037778>"
EMOJI_WINTER_END = "<:GhirlandaOro:1499887262404706546>"


# ---------------------------------------------------
# UTILS
# ---------------------------------------------------

def parse_datetime(value: str):
    return datetime.strptime(value, "%d-%m-%Y %H:%M")


def to_iso(dt: datetime):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def from_iso(value: str, tz="Europe/Rome"):
    return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo(tz))


# ---------------------------------------------------
# EMBED
# ---------------------------------------------------

def get_event_emojis(event_name: str, event: dict):
    if event_name == "Mercato Maji":
        return EMOJI_MAJI_START, EMOJI_MAJI_END
    if event_name == "Festival delle Luci d’Inverno":
        return EMOJI_WINTER_START, EMOJI_WINTER_END
    return event.get("emoji", ""), event.get("emoji_end", "")


def build_start_embed(event: dict, recovered=False):
    start_dt = from_iso(event["start"], event["timezone"])
    start_ts = int(start_dt.timestamp())

    now = datetime.now(ZoneInfo(event["timezone"]))
    countdown = "00:00" if now >= start_dt else f"<t:{start_ts}:R>"

    emoji_start, emoji_end = get_event_emojis(event["name"], event)

    embed = discord.Embed(
        title=f"{emoji_start} {event['name']} {emoji_end}".strip(),
        description="",
        color=int(event.get("color", "#FFD700").replace("#", "0x"), 16)
    )

    embed.add_field(name="", value=f"<@&{MENTION_ROLE_ID}>", inline=False)

    embed.add_field(
        name="",
        value=(
            f"{event['description']}\n\n"
            f"L'evento inizierà alle <t:{start_ts}:t>!\n"
            f"**Countdown:** {countdown}"
        ),
        inline=False
    )

    footer = "Evento dinamico — Recuperato" if recovered else "Evento dinamico"
    embed.set_footer(text=footer)
    return embed


def build_end_embed(event: dict, recovered=False):
    end_dt = from_iso(event["end"], event["timezone"])
    end_ts = int(end_dt.timestamp())

    now = datetime.now(ZoneInfo(event["timezone"]))
    countdown = "00:00" if now >= end_dt else f"<t:{end_ts}:R>"

    emoji_start, emoji_end = get_event_emojis(event["name"], event)

    embed = discord.Embed(
        title=f"{emoji_start} {event['name']} {emoji_end}".strip(),
        description="",
        color=int(event.get("color", "#FFD700").replace("#", "0x"), 16)
    )

    embed.add_field(name="", value=f"<@&{MENTION_ROLE_ID}>", inline=False)

    embed.add_field(
        name="",
        value=(
            f"L'evento terminerà alle <t:{end_ts}:t>!\n"
            f"**Countdown:** {countdown}"
        ),
        inline=False
    )

    footer = "Evento dinamico — Recuperato" if recovered else "Evento dinamico"
    embed.set_footer(text=footer)
    return embed


# ---------------------------------------------------
# COG
# ---------------------------------------------------

class DynamicEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.state = self.load_state()
        self.load_events()

    # ---------------------------
    # CARICAMENTO / SALVATAGGIO
    # ---------------------------

    def load_events(self):
        try:
            with open(DYNAMIC_EVENTS_FILE, "r", encoding="utf-8") as f:
                self.events = json.load(f)
            print("[DynamicEvents] Eventi caricati dal file dinamico.")
        except Exception as e:
            print(f"[DynamicEvents] Nessun file eventi dinamici o errore nel caricamento: {e}")
            self.events = []

    def save_events(self):
        with open(DYNAMIC_EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2)
        print("[DynamicEvents] Eventi dinamici salvati su file.")

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = {}
        else:
            state = {}

        if "dynamic" not in state:
            state["dynamic"] = {}

        return state

    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=4)

    # ---------------------------
    # COMANDO /addevents
    # ---------------------------

    @app_commands.command(name="addevents", description="Aggiunge un evento dinamico")
    @app_commands.describe(
        nome="Nome dell'evento",
        descrizione="Descrizione dell'evento",
        inizio="Inserire GG-MM-AAAA HH:MM",
        fine="Inserire GG-MM-AAAA HH:MM"
    )
    async def add_event(
        self,
        interaction: discord.Interaction,
        nome: str,
        descrizione: str,
        inizio: str,
        fine: str
    ):
        try:
            dt_start = parse_datetime(inizio).replace(tzinfo=ZoneInfo("Europe/Rome"))
        except Exception:
            await interaction.response.send_message(
                "❌ Formato INIZIO non valido. Usa **GG-MM-AAAA HH:MM**",
                ephemeral=True
            )
            return

        try:
            dt_end = parse_datetime(fine).replace(tzinfo=ZoneInfo("Europe/Rome"))
        except Exception:
            await interaction.response.send_message(
                "❌ Formato FINE non valido. Usa **GG-MM-AAAA HH:MM**",
                ephemeral=True
            )
            return

        now = datetime.now(ZoneInfo("Europe/Rome"))

        event = {
            "name": nome,
            "description": descrizione,
            "start": to_iso(dt_start),
            "end": to_iso(dt_end),
            "timezone": "Europe/Rome",
            "color": "#FFD700",
            "start_message_id": None,
            "end_message_id": None,
            "recovered_start": False
        }

        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)

        # Evento FUTURO
        if now < dt_start:
            embed = build_start_embed(event, recovered=False)
            msg = await channel.send(embed=embed)
            event["start_message_id"] = msg.id

        # Evento già INIZIATO
        elif dt_start <= now < dt_end:
            embed = build_start_embed(event, recovered=True)
            msg = await channel.send(embed=embed)
            event["start_message_id"] = msg.id
            event["recovered_start"] = True

        # Evento già FINITO
        else:
            embed_start = build_start_embed(event, recovered=True)
            msg_start = await channel.send(embed=embed_start)
            event["start_message_id"] = msg_start.id
            event["recovered_start"] = True

            embed_end = build_end_embed(event, recovered=True)
            msg_end = await channel.send(embed=embed_end)
            event["end_message_id"] = msg_end.id

        self.events.append(event)
        self.save_events()

        await interaction.response.send_message(
            f"Evento dinamico **{nome}** aggiunto.",
            ephemeral=True
        )

    # ---------------------------
    # LOOP: RECUPERO EVENTI PERSI
    # ---------------------------

    @tasks.loop(seconds=30)
    async def recover_missed_events(self):
        now = datetime.now(ZoneInfo("Europe/Rome"))
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)

        changed_events = False
        dynamic_state = self.state.get("dynamic", {})

        for event in self.events:
            start_dt = from_iso(event["start"], event["timezone"])
            end_dt = from_iso(event["end"], event["timezone"])

            event_id = id(event)
            if str(event_id) not in dynamic_state:
                dynamic_state[str(event_id)] = {
                    "start_recovered": False,
                    "end_recovered": False
                }

            entry = dynamic_state[str(event_id)]

            # Recupero START
            if now > start_dt and not event["start_message_id"] and not entry["start_recovered"]:
                embed = build_start_embed(event, recovered=True)
                msg = await channel.send(embed=embed)
                event["start_message_id"] = msg.id
                event["recovered_start"] = True
                entry["start_recovered"] = True
                changed_events = True

            # Recupero END
            if now > end_dt and not event["end_message_id"] and not entry["end_recovered"]:
                embed = build_end_embed(event, recovered=True)
                msg = await channel.send(embed=embed)
                event["end_message_id"] = msg.id
                entry["end_recovered"] = True
                changed_events = True

        self.state["dynamic"] = dynamic_state

        if changed_events:
            self.save_events()
            self.save_state()

    @recover_missed_events.before_loop
    async def before_recover(self):
        await self.bot.wait_until_ready()

    # ---------------------------
    # LOOP: ANNUNCIO FINE
    # ---------------------------

    @tasks.loop(minutes=1)
    async def check_end_announcements(self):
        now = datetime.now(ZoneInfo("Europe/Rome"))
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)

        changed = False

        for event in self.events:
            if event.get("end_message_id"):
                continue

            end_dt = from_iso(event["end"], event["timezone"])
            announce_dt = end_dt - timedelta(days=1)
            announce_dt = announce_dt.replace(hour=18, minute=0, second=0)

            if now >= announce_dt:
                embed = build_end_embed(event)
                msg = await channel.send(embed=embed)
                event["end_message_id"] = msg.id
                changed = True

        if changed:
            self.save_events()

    @check_end_announcements.before_loop
    async def before_check_end(self):
        await self.bot.wait_until_ready()

    # ---------------------------
    # LOOP: COUNTDOWN
    # ---------------------------

    @tasks.loop(seconds=30)
    async def update_countdowns(self):
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)

        for event in self.events:
            msg_id = event.get("start_message_id")
            if msg_id:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=build_start_embed(event))

            end_msg_id = event.get("end_message_id")
            if end_msg_id:
                msg = await channel.fetch_message(end_msg_id)
                await msg.edit(embed=build_end_embed(event, recovered=event.get("recovered_start", False)))

    @update_countdowns.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

    # ---------------------------
    # LOOP: CLEANUP
    # ---------------------------

    @tasks.loop(minutes=5)
    async def cleanup_events(self):
        now = datetime.now(ZoneInfo("Europe/Rome"))
        new_list = []

        for event in self.events:
            end_dt = from_iso(event["end"], event["timezone"])
            if now < end_dt:
                new_list.append(event)

        if len(new_list) != len(self.events):
            self.events = new_list
            self.save_events()

    @cleanup_events.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    # ---------------------------
    # AVVIO LOOP IN on_ready
    # ---------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.recover_missed_events.is_running():
            self.recover_missed_events.start()

        if not self.check_end_announcements.is_running():
            self.check_end_announcements.start()

        if not self.update_countdowns.is_running():
            self.update_countdowns.start()

        if not self.cleanup_events.is_running():
            self.cleanup_events.start()


async def setup(bot):
    await bot.add_cog(DynamicEvents(bot))
