import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json

DYNAMIC_EVENTS_FILE = "dynamic_events.json"
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


def build_start_embed(event: dict):
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

    embed.set_footer(text="Evento dinamico")
    return embed


def build_end_embed(event: dict):
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
            f"L'evento terminerà domani alle <t:{end_ts}:t>!\n"
            f"**Countdown:** {countdown}"
        ),
        inline=False
    )

    embed.set_footer(text="Evento dinamico")
    return embed


# ---------------------------------------------------
# COG
# ---------------------------------------------------

class DynamicEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.load_events()
        self.cleanup_events.start()
        self.check_end_announcements.start()
        self.update_countdowns.start()

    # ---------------------------
    # CARICAMENTO / SALVATAGGIO
    # ---------------------------

    def load_events(self):
        try:
            with open(DYNAMIC_EVENTS_FILE, "r", encoding="utf-8") as f:
                self.events = json.load(f)
        except:
            self.events = []

    def save_events(self):
        with open(DYNAMIC_EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2)

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
            dt_start = parse_datetime(inizio)
        except:
            await interaction.response.send_message(
                "❌ Formato INIZIO non valido. Usa **GG-MM-AAAA HH:MM**",
                ephemeral=True
            )
            return

        try:
            dt_end = parse_datetime(fine)
        except:
            await interaction.response.send_message(
                "❌ Formato FINE non valido. Usa **GG-MM-AAAA HH:MM**",
                ephemeral=True
            )
            return

        event = {
            "name": nome,
            "description": descrizione,
            "start": to_iso(dt_start),
            "end": to_iso(dt_end),
            "timezone": "Europe/Rome",
            "color": "#FFD700",
            "end_announced": False,
            "start_message_id": None,
            "end_message_id": None
        }

        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)

        embed = build_start_embed(event)
        msg = await channel.send(embed=embed)
        event["start_message_id"] = msg.id

        # Aggiorna subito il countdown
        await msg.edit(embed=build_start_embed(event))

        self.events.append(event)
        self.save_events()

        await interaction.response.send_message(
            f"Evento dinamico **{nome}** aggiunto.",
            ephemeral=True
        )

    # ---------------------------
    # ANNUNCIO FINE EVENTO
    # ---------------------------

    @tasks.loop(minutes=1)
    async def check_end_announcements(self):
        now = datetime.now(ZoneInfo("Europe/Rome"))
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)

        changed = False

        for event in self.events:
            if event["end_announced"]:
                continue

            end_dt = from_iso(event["end"], event["timezone"])
            announce_dt = end_dt - timedelta(days=1)
            announce_dt = announce_dt.replace(hour=18, minute=0, second=0)

            if now >= announce_dt:
                embed = build_end_embed(event)
                msg = await channel.send(embed=embed)
                event["end_message_id"] = msg.id
                event["end_announced"] = True
                changed = True

        if changed:
            self.save_events()

    # ---------------------------
    # AGGIORNAMENTO COUNTDOWN
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
                await msg.edit(embed=build_end_embed(event))

    # ---------------------------
    # CLEANUP
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
            print("Eventi dinamici scaduti rimossi.")

    @cleanup_events.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(DynamicEvents(bot))
