import datetime
import asyncio
import discord
from discord.ext import commands, tasks
import time
import os

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


# === TEMPO COSMETICO INTEGRATO NEL MAIN ===

last_visual_seconds = None
last_visual_real = None
VISUAL_RATIO = 2.5   # 1 minuto Palia = 2.5 secondi reali

def compute_palia_time():
    global last_visual_seconds, last_visual_real

    now = time.time()

    # Tempo reale di Palia
    epoch = now
    real_palia_seconds = (epoch * 24) % 86400

    # Prima chiamata
    if last_visual_seconds is None:
        last_visual_seconds = real_palia_seconds
        last_visual_real = now

    # Delta reale
    delta_real = now - last_visual_real
    delta_palia_minutes = delta_real / VISUAL_RATIO
    delta_palia_seconds = delta_palia_minutes * 60

    cosmetic = (last_visual_seconds + delta_palia_seconds) % 86400

    # Aggancia sempre al tempo reale se è avanti
    if real_palia_seconds > cosmetic:
        cosmetic = real_palia_seconds

    last_visual_seconds = cosmetic
    last_visual_real = now

    hour = int(cosmetic // 3600)
    minute = int((cosmetic % 3600) // 60)
    display_hour = hour % 12 or 12
    suffix = "AM" if hour < 12 else "PM"

    return hour, minute, display_hour, suffix


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


# === RINOMINA CANALE (BLOCCHI 3 ORE) ===

last_block = None

@tasks.loop(seconds=60)   # leggerissimo, preciso
async def update_channel():
    global last_block

    channel_id = 1483229095738212533
    channel = bot.get_channel(channel_id)
    if channel is None:
        return

    # Otteniamo l'ora cosmetica reale di Palia
    hour, minute, display_hour, suffix = compute_palia_time()

    # Calcolo blocco attuale
    current_block = round_to_3_hours(hour)

    # Se il blocco non è cambiato → non fare nulla
    if current_block == last_block:
        return

    # Aggiorna blocco
    last_block = current_block

    # Calcolo nome canale
    rounded_display = current_block % 12 or 12
    rounded_suffix = "AM" if current_block < 12 else "PM"
    phase, icon_uni = get_phase(current_block)

    new_name = f"{icon_uni} {rounded_display}:00 {rounded_suffix} — {phase}"

    try:
        await channel.edit(name=new_name)
    except Exception as e:
        print(f"Errore aggiornamento canale: {e}")


# === AVVIO BOT ===

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
