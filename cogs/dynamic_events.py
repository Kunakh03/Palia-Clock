import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
from zoneinfo import ZoneInfo
import json

DYNAMIC_EVENTS_FILE = "dynamic_events.json"
ANNOUNCE_CHANNEL_ID = 1483229095738212533


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


# ---------------------------------------------------
# COG EVENTI DINAMICI
# ---------------------------------------------------

class DynamicEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = []
        self.load_events()
        self.cleanup_events.start()

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
    # SLASH COMMAND /addevents
    # ---------------------------

    @app_commands.command(name="addevents", description="Aggiunge un evento dinamico")
    async def add_event(self, interaction: discord.Interaction, nome: str, descrizione: str, data: str):
        """
        /addevents nome descrizione data
        data = formato italiano: GG-MM-AAAA HH:MM
        """

        # --- VALIDAZIONE DATA IN FORMATO ITALIANO ---
        try:
            # Converte "GG-MM-AAAA HH:MM" → datetime
            dt = datetime.strptime(data, "%d-%m-%Y %H:%M")

            # Converte in ISO standard per il JSON
            data_iso = dt.strftime("%Y-%m-%dT%H:%M:%S")

        except ValueError:
            await interaction.response.send_message(
                "❌ Formato data non valido.\n"
                "Usa **GG-MM-AAAA HH:MM**\n"
                "Esempio: `05-05-2026 09:00`",
                ephemeral=True
            )
            return

        # Evento dinamico
        event = {
            "name": nome,
            "description": descrizione,
            "start": data_iso,
            "timezone": "Europe/Rome",
            "color": "#FFD700"
        }

        self.events.append(event)
        self.save_events()

        embed = build_dynamic_embed(event)
        channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"Evento dinamico **{nome}** aggiunto e annunciato.",
            ephemeral=True
        )

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
                start_dt = datetime.fromisoformat(event["start"]).replace(
                    tzinfo=ZoneInfo(event.get("timezone", "Europe/Rome"))
                )
            except Exception:
                # Evento corrotto → lo eliminiamo
                changed = True
                continue

            if now < start_dt:
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
