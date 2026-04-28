import json
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands


class NPCMoves(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        with open("npc_schedule.json", "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.fancy_map = {
            "A": "𝐴", "B": "𝐵", "C": "𝐶", "D": "𝐷", "E": "𝐸", "F": "𝐹", "G": "𝐺",
            "H": "𝐻", "I": "𝐼", "J": "𝐽", "K": "𝐾", "L": "𝐿", "M": "𝑀", "N": "𝑁",
            "O": "𝑂", "P": "𝑃", "Q": "𝑄", "R": "𝑅", "S": "𝑆", "T": "𝑇", "U": "𝑈",
            "V": "𝑉", "W": "𝑊", "X": "𝑋", "Y": "𝑌", "Z": "𝑍",
            "a": "𝑎", "b": "𝑏", "c": "𝑐", "d": "𝑑", "e": "𝑒", "f": "𝑓", "g": "𝑔",
            "h": "ℎ", "i": "𝑖", "j": "𝑗", "k": "𝑘", "l": "𝑙", "m": "𝑚", "n": "𝑛",
            "o": "𝑜", "p": "𝑝", "q": "𝑞", "r": "𝑟", "s": "𝑠", "t": "𝑡", "u": "𝑢",
            "v": "𝑣", "w": "𝑤", "x": "𝑥", "y": "𝑦", "z": "𝑧"
        }

    def fancy(self, text: str) -> str:
        return "".join(self.fancy_map.get(c, c) for c in text)

    async def npc_autocomplete(self, interaction, current: str):
        current = current.lower()
        results = []

        for key, npc in self.data.items():
            name = npc["name"].lower()
            if current in key.lower() or current in name:
                results.append(app_commands.Choice(name=npc["name"], value=key))

        return results[:25]

    def get_current_location(self, schedule):
        now = datetime.utcnow()
        now_minutes = now.hour * 60 + now.minute

        for entry in schedule:
            t1 = entry["from"].replace(" AM", "").replace(" PM", "")
            t2 = entry["to"].replace(" AM", "").replace(" PM", "")

            h1, m1 = map(int, t1.split(":"))
            h2, m2 = map(int, t2.split(":"))

            start = h1 * 60 + m1
            end = h2 * 60 + m2

            if start < end:
                if start <= now_minutes < end:
                    return entry
            else:
                if now_minutes >= start or now_minutes < end:
                    return entry

        return None

    def format_time(self, t: str) -> str:
        if "AM" in t or "PM" in t:
            return t
        h, m = map(int, t.split(":"))
        suffix = "AM" if h < 12 else "PM"
        h = h % 12 or 12
        return f"{h}:{m:02d} {suffix}"

    @app_commands.command(name="npc", description="Mostra la routine di un personaggio")
    @app_commands.describe(nome="Cerca per nome")
    @app_commands.autocomplete(nome=npc_autocomplete)
    async def npc(self, interaction: discord.Interaction, nome: str):
        npc = self.data.get(nome)
        if not npc:
            await interaction.response.send_message("Personaggio non trovato.", ephemeral=True)
            return

        schedule = npc.get("schedule", [])
        notes = npc.get("notes", [])
        current = self.get_current_location(schedule)
        fancy_name = self.fancy(npc["name"])

        lines = [f"# {npc['emoji']}   __{fancy_name}__"]

        if current:
            lines.append(f"Posizione attuale: **{current['location_short']}**")

        if schedule:
            lines.append("\n**Routine giornaliera**")
            for e in schedule:
                lines.append(f"• **{self.format_time(e['from'])}** → {e['location_full']}")

        if notes:
            lines.append("\n**Note**")
            lines.append("\n".join(notes))

        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot):
    await bot.add_cog(NPCMoves(bot))
