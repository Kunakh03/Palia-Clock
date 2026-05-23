import datetime
import discord
from discord.ext import commands, tasks
import time
import os

# === IMPORT TEMPO COSMETICO DAL COG ===
from cogs.paliatime import compute_palia_time

intents = discord.Intents.default()
intents.message_content = True


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=1483279761689149470
        )

    async def setup_hook(self):
        # Caricamento COG
        await self.load_extension("cogs.paliatime")
        await self.load_extension("cogs.npc")
        await self.load_extension("cogs.static_events")
        await self.load_extension("cogs.dynamic_events")

        # Sync comandi
        synced = await self.tree.sync()
        print("Comandi sincronizzati:", [cmd.name for cmd in synced])

        # Avvio loop canale orario
        if not update_channel.is_running():
            update_channel.start()


bot = MyBot()


# === UTILS ===

def round_to_3_hours(hour):
    return (hour // 3) * 3


EMOJI_MATTINO_UNI = "🌅"
EMOJI_GIORNO_UNI = "🌞"
EMOJI_SERA_UNI = "🌇"
EMOJI_NOTTE_UNI = "🌙"


def get_phase(hour):
    if 3 <= hour < 6:
        return "Mattino", EMOJI_MATTINO_UNI
    elif 6 <= hour < 18:
        return "Giorno", EMOJI_GIORNO_UNI
    elif 18 <= hour < 21:
        return "Sera", EMOJI_SERA_UNI
    else:
        return "Notte", EMOJI_NOTTE_UNI


# === RINOMINA CANALE (NUOVO SISTEMA ORARIO) ===

last_name = None

@tasks.loop(seconds=360)   # ogni 6 minuti reali
async def update_channel():
    global last_name

    channel_id = 1483229095738212533
    channel = bot.get_channel(channel_id)
    if channel is None:
        return

    # Otteniamo l'ora cosmetica reale di Palia
    hour, minute, display_hour, suffix = compute_palia_time()

    # Arrotondamento ai blocchi di 3 ore
    rounded_hour = round_to_3_hours(hour)
    rounded_display = rounded_hour % 12 or 12
    rounded_suffix = "AM" if rounded_hour < 12 else "PM"

    # Fase del giorno (Mattino/Giorno/Sera/Notte)
    phase, icon_uni = get_phase(rounded_hour)

    new_name = f"{icon_uni} {rounded_display}:00 {rounded_suffix} — {phase}"

    if new_name == last_name:
        return

    try:
        await channel.edit(name=new_name)
        last_name = new_name
    except Exception as e:
        print(f"Errore aggiornamento canale: {e}")


# === AVVIO BOT ===

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
