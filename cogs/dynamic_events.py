import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json

DYNAMIC_EVENTS_FILE = "dynamic_events.json"
ANNOUNCE_CHANNEL_ID = 1416482590596141248  # canale annunci


# ---------------------------------------------------
# EMBED PER EVENTI DINAMICI
# ---------------------------------------------------

def build_dynamic_embed(event: dict):
    tz = ZoneInfo(event.get("timezone", "Europe/Rome"))
    start_dt = datetime.fromisoformat(event["start"]).replace(tzinfo=tz)
    start_ts = int(start_dt.timestamp())

    title = event["name"]

    description = (
        f"{event['description']}\n\n"
        f"**Inizio:** <t:{start_ts}:t>\n"
        f"**Countdown:** <t:{start_ts}:R>"
    )

    embed = discord.Embed(
        title=title,
        description=description,
        color=int(event.get("color", "#FFD700").replace("#", "0x"), 16)
    )

    embed.set_footer(text="Palia Clock • Evento dinamico")
    return embed


def build_end_announcement(event: dict):
    tz = ZoneInfo(event.get("timezone", "Europe/Rome"))
    end_dt = datetime.fromisoformat(event["end"]).replace(tzinfo=tz)
    end_ts = int(end_dt.timestamp())

    embed = discord.Embed(
        title=f"📌 Fine evento: {event['name']}",
        description=(
            f"L'evento terminerà alle <t:{end_ts}:t>!\n"
            f"**Countdown:** <t:{end_ts}:R>"
        ),
        color=0xe67e22
    )

    embed.set_footer(text="Palia Clock • Evento dinamico")
    return embed


# ---------------------------------------------------
# COG EVENTI DINAMICI
# ---------------------------------------------------

class DynamicEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.load_events()
        self.cleanup_events.start()
        self.check_end_announcements.start()

    # ---------------------------
    # CARICAMENTO / SALVATAGGIO
    # ---------------------------

    def load_events(self):
        try:
            with open(DYNAMIC_EVENTS_FILE, "r", encoding="utf-8") as f:
                self.events = json.load(f)
        except Exception:
            self.events = []

    def save_events(self):
        with open(DYNAMIC_EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2)

    # ---------------------------
    # AUTOCOMPLETE GUIDATO
    # ---------------------------

    @staticmethod
    def autocomplete_hint():
        return [
            app_commands.Choice(
                name="Inserire nel formato: GG-MM-AAAA HH:MM",
                value="GG-MM-AAAA HH:MM"
            )
        ]

    # ---------------------------
    # SLASH COMMAND /addevents
    # ---------------------------

    @app_commands.command(name="addevents", description="Aggiunge un evento dinamico")
    @app_commands.describe(
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
        """
        /addevents nome descrizione inizio fine
        """

        # --- VALIDAZIONE INIZIO ---
        try:
            dt_start = datetime.strptime(inizio, "%d-%m-%Y %H:%M")
            start_iso = dt_start.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            await interaction.response.send_message(
                "❌ Formato data INIZIO non valido.\n"
                "Usa **GG-MM-AAAA HH:MM**",
                ephemeral=True
            )
            return

        # --- VALIDAZIONE FINE ---
        try:
            dt_end = datetime.strptime(fine, "%d-%m-%Y %H:%M")
            end_iso = dt_end.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            await interaction.response.send_message(
                "❌ Formato data FINE non valido.\n"
                "Usa **GG-MM-AAAA HH:MM**",
                ephemeral=True
            )
            return

        # Evento dinamico
        event = {
            "name": nome,
            "description": descrizione,
            "start": start_iso,
            "end": end_iso,
            "timezone": "Europe/Rome",
            "color": "#FFD700",
            "end_announced": False
        }

        self.events.append(event)
        self.save_events()

        # Annuncio immediato dell'inizio
        embed = build_dynamic_embed(event)
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)

        if channel is None:
            print("ERRORE: Canale annunci non trovato.")
            await interaction.response.send_message(
                "❌ Errore: canale annunci non trovato.",
                ephemeral=True
            )
            return

        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"Evento dinamico **{nome}** aggiunto e annunciato.",
            ephemeral=True
        )

    # ---------------------------
    # AUTOCOMPLETE PER INIZIO E FINE
    # ---------------------------

    @add_event.autocomplete("inizio")
    async def autocomplete_inizio(self, interaction, current):
        return self.autocomplete_hint()

    @add_event.autocomplete("fine")
    async def autocomplete_fine(self, interaction, current):
        return self.autocomplete_hint()

    # ---------------------------
    # ANNUNCIO FINE EVENTO (giorno prima alle 18:00)
    # ---------------------------

    @tasks.loop(minutes=1)
    async def check_end_announcements(self):
        now = datetime.now(ZoneInfo("Europe/Rome"))
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if channel is None:
            return

        changed = False

        for event in self.events:
            if event.get("end_announced"):
                continue

            end_dt = datetime.fromisoformat(event["end"]).replace(
                tzinfo=ZoneInfo(event["timezone"])
            )

            announce_dt = end_dt - timedelta(days=1)
            announce_dt = announce_dt.replace(hour=18, minute=0, second=0, microsecond=0)

            if now >= announce_dt:
                embed = build_end_announcement(event)
                await channel.send(embed=embed)
                event["end_announced"] = True
                changed = True

        if changed:
            self.save_events()

    # ---------------------------
    # CANCELLAZIONE AUTOMATICA
    # ---------------------------

    @tasks.loop(minutes=5)
    async def cleanup_events(self):
        now = datetime.now(ZoneInfo("Europe/Rome"))
        changed = False

        new_list = []
        for event in self.events:
            try:
                end_dt = datetime.fromisoformat(event["end"]).replace(
                    tzinfo=ZoneInfo(event.get("timezone", "Europe/Rome"))
                )
            except Exception:
                changed = True
                continue

            if now < end_dt:
                new_list.append(event)
            else:
                changed = True

        if changed:
            self.events = new_list
            self.save_events()
            print("Eventi dinamici scaduti o invalidi rimossi.")

    @cleanup_events.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(DynamicEvents(bot))
