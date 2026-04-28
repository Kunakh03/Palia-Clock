import time
import discord
from discord.ext import commands
from discord import app_commands

# Emojis
EMOJI_MATTINO = "<:Mattino:1489971777823309834>"
EMOJI_GIORNO  = "<:Giorno:1489971730012442705>"
EMOJI_SERA    = "<:Sera:1489971681006063728>"
EMOJI_NOTTE   = "<:Notte:1489971620930912318>"

# Tempo cosmetico locale al COG
last_visual_seconds = None
last_visual_real = None
VISUAL_RATIO = 2.5   # 1 minuto Palia = 2.5 secondi reali

def get_phase(hour):
    if 3 <= hour < 6:
        return "Mattino", EMOJI_MATTINO
    elif 6 <= hour < 18:
        return "Giorno", EMOJI_GIORNO
    elif 18 <= hour < 21:
        return "Sera", EMOJI_SERA
    else:
        return "Notte", EMOJI_NOTTE

def compute_palia_time():
    global last_visual_seconds, last_visual_real

    now = time.time()

    # Tempo reale di Palia (semplice, come prima)
    epoch = now
    real_palia_seconds = (epoch * 24) % 86400

    # Prima chiamata → usa il reale
    if last_visual_seconds is None:
        last_visual_seconds = real_palia_seconds
        last_visual_real = now

    # Delta reale tra comandi
    delta_real = now - last_visual_real
    delta_palia_minutes = delta_real / VISUAL_RATIO
    delta_palia_seconds = delta_palia_minutes * 60

    cosmetic = (last_visual_seconds + delta_palia_seconds) % 86400

    # Se il tempo reale è avanti → usa quello
    if real_palia_seconds > cosmetic:
        last_visual_seconds = real_palia_seconds
        last_visual_real = now
    else:
        last_visual_seconds = cosmetic
        last_visual_real = now

    hour = int(last_visual_seconds // 3600)
    minute = int((last_visual_seconds % 3600) // 60)
    display_hour = hour % 12 or 12
    suffix = "AM" if hour < 12 else "PM"

    return hour, minute, display_hour, suffix

class PaliaTime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="paliatime", description="Mostra l'ora attuale in Palia")
    async def paliatime(self, interaction: discord.Interaction):

        hour, minute, display_hour, suffix = compute_palia_time()
        phase, icon = get_phase(hour)

        await interaction.response.send_message(
            f"{icon}    **{display_hour}:{minute:02d} {suffix}** — {phase}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(PaliaTime(bot))
