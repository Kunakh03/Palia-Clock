import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json

DYNAMIC_EVENTS_FILE = "dynamic_events.json"
ANNOUNCE_CHANNEL_ID = 1416482590596141248   # <-- ID aggiornato


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
    # AUTOCOMPLETE PER LA DATA
    # ---------------------------

    @app_commands.autocomplete(data=True)
    async def autocomplete_data(self, interaction: discord.Interaction, current: str):
        """
        Suggerisce date in formato italiano mentre si digita.
        """
        now = datetime.now()

        suggestions = []

        # Oggi + orari comuni
        for hour in [now.hour + 1, 18, 21]:
            try:
                dt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                if dt > now:
                    label = dt.strftime("%d-%m-%Y %H:%M")
                    suggestions.append(app_commands.Choice(name=f"Oggi alle {dt.strftime('%H:%M')}", value=label))
            except:
                pass

        # Domani 09:00
        tomorrow = now + timedelta(days=1)
        dt_tomorrow = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        suggestions.append(app_commands.Choice(
            name=f"Domani alle 09:00",
            value=dt_tomorrow.strftime("%d-%m-%Y %H:%M")
        ))

        # Tra 1 ora
        dt_1h = now + timedelta(hours=1)
        suggestions.append(app_commands.Choice(
            name=f"Tra 1 ora ({dt_1h.strftime('%H:%M')})",
            value=dt_1h.strftime("%d-%m-%Y %H:%M")
        ))

        # Filtra per ciò che l'utente sta digitando
        if current:
            suggestions = [s for s in suggestions if current in s.value]

        return suggestions[:25]

    # ---------------------------
    # SLASH COMMAND /addevents
    # ---------------------------

    @app_commands.command(name="addevents", description="Aggiunge un evento dinamico")
    @app_commands.autocomplete(data=autocomplete_data)
    async def add_event(self, interaction: discord.Interaction, nome: str, descrizione: str, data: str):
        """
        /addevents nome descrizione data
        data = formato italiano: GG-MM-AAAA HH:MM
        """

        # --- VALIDAZIONE DATA IN FORMATO ITALIANO ---
        try:
            dt = datetime.strptime(data, "%d-%m-%Y %H:%M")
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

        if channel is None:
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
