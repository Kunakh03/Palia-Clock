import datetime
import discord
from discord.ext import commands, tasks
import time

# === OROLOGIO INTERNO DI PALIA ===

internal_palia_seconds = None      # tempo interno reale
last_update_real = None            # timestamp reale dell'ultimo aggiornamento
palia_speed = 24.0                 # velocità interna (correggibile)

# === TEMPO COSMETICO (solo visualizzazione) ===

last_visual_seconds = None         # ultimo tempo mostrato
last_visual_real_time = None       # quando è stato mostrato
VISUAL_RATIO = 2.0                 # 1 minuto Palia = 2 secondi reali (non usato dal COG ora)

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
        await self.load_extension("cogs.paliatime")
        await self.load_extension("cogs.npc")
        await self.load_extension("cogs.events")
        await self.load_extension("cogs.dynamic_events")

        synced = await self.tree.sync()
        print("Comandi sincronizzati:", [cmd.name for cmd in synced])


bot = MyBot()


# === INIZIALIZZAZIONE OROLOGIO ===

def initialize_palia_clock():
    global internal_palia_seconds, last_update_real
    epoch = time.time()
    internal_palia_seconds = (epoch * 24) % 86400
    last_update_real = epoch


# === AGGIORNAMENTO OROLOGIO INTERNO ===

def update_internal_clock():
    global internal_palia_seconds, last_update_real

    now = time.time()
    delta_real = now - last_update_real

    internal_palia_seconds = (internal_palia_seconds + delta_real * palia_speed) % 86400
    last_update_real = now


# === CORREZIONE MORBIDA DELLA VELOCITÀ ===

@tasks.loop(seconds=10)
async def smooth_sync():
    global palia_speed, internal_palia_seconds

    epoch = time.time()
    perfect = (epoch * 24) % 86400

    update_internal_clock()

    diff = (perfect - internal_palia_seconds + 86400) % 86400
    if diff > 43200:
        diff -= 86400

    if abs(diff) < 60:
        return

    correction = diff / 600.0
    correction = max(min(correction, 0.5), -0.5)

    palia_speed = 24.0 + correction


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


# === RINOMINA CANALE ===

last_name = None

@tasks.loop(seconds=360)
async def update_channel():
    global last_name

    channel_id = 1483229095738212533
    channel = bot.get_channel(channel_id)
    if channel is None:
        return

    update_internal_clock()

    hour = int(internal_palia_seconds // 3600)
    rounded_hour = round_to_3_hours(hour)
    rounded_display = rounded_hour % 12 or 12
    rounded_suffix = "AM" if rounded_hour < 12 else "PM"

    phase, icon_uni = get_phase(rounded_hour)

    new_name = f"{icon_uni} {rounded_display}:00 {rounded_suffix} — {phase}"

    if new_name == last_name:
        return

    try:
        await channel.edit(name=new_name)
        last_name = new_name
    except Exception as e:
        print(f"Errore aggiornamento canale: {e}")


# === ON_READY ===

@bot.event
async def on_ready():
    print(f"Connesso come {bot.user}")
    print("Guilds:", [(g.name, g.id) for g in bot.guilds])

    initialize_palia_clock()

    if not update_channel.is_running():
        update_channel.start()

    if not smooth_sync.is_running():
        smooth_sync.start()


# === AVVIO BOT ===

import os
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
