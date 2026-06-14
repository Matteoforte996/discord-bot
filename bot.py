import discord
from discord.ext import commands, tasks
import aiosqlite
import time

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import os

def run_web():
    port = int(os.environ.get("PORT", 10000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

threading.Thread(target=run_web).start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

DB_PATH = "activity.db"


# =========================
# DATABASE INIT
# =========================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS activity (
                user_id TEXT PRIMARY KEY,
                last_seen REAL
            )
        """)
        await db.commit()


# =========================
# SAFE UPDATE (FIX IMPORTANTE)
# =========================
async def set_activity(user_id: int, timestamp: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO activity (user_id, last_seen)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET last_seen =
                CASE
                    WHEN excluded.last_seen > last_seen THEN excluded.last_seen
                    ELSE last_seen
                END
        """, (str(user_id), timestamp))
        await db.commit()


async def get_activity(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT last_seen FROM activity WHERE user_id=?",
            (str(user_id),)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


# =========================
# START BOT
# =========================
@bot.event
async def on_ready():
    await init_db()
    backup_scan.start()
    print(f"Connesso come {bot.user}")


# =========================
# LIVE TRACKING
# =========================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await set_activity(message.author.id, time.time())

    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    await set_activity(user.id, time.time())


# =========================
# BACKUP AUTOMATICO (FIX ERRORI)
# =========================
@tasks.loop(minutes=30)
async def backup_scan():
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                async for msg in channel.history(limit=50):
                    if msg.author.bot:
                        continue

                    await set_activity(msg.author.id, msg.created_at.timestamp())

            except:
                continue


# =========================
# SCAN MANUALE
# =========================
@bot.command()
@commands.has_permissions(administrator=True)
async def rescan(ctx):
    await ctx.send("🔄 Scan in corso...")

    count = 0

    for channel in ctx.guild.text_channels:
        try:
            async for msg in channel.history(limit=None):
                if msg.author.bot:
                    continue

                await set_activity(msg.author.id, msg.created_at.timestamp())
                count += 1

        except:
            continue

    await ctx.send(f"✅ Scan completato: {count} messaggi")


# =========================
# DASHBOARD
# =========================
@bot.command()
@commands.has_permissions(administrator=True)
async def analisi(ctx, giorni: int = 30):
    threshold = time.time() - (giorni * 86400)

    attivi = []
    inattivi = []

    for member in ctx.guild.members:
        if member.bot:
            continue

        last = await get_activity(member.id)

        if last is None:
            inattivi.append((member.display_name, "Mai attivo"))
            continue

        diff_days = int((time.time() - last) / 86400)

        if last >= threshold:
            attivi.append((member.display_name, diff_days))
        else:
            inattivi.append((member.display_name, diff_days))


    attivi.sort(key=lambda x: x[1])
    inattivi.sort(key=lambda x: (999999 if x[1] == "Mai attivo" else x[1]), reverse=True)


    embed = discord.Embed(
        title="📊 Analisi attività server",
        description=f"Ultimi {giorni} giorni",
        color=discord.Color.blurple()
    )

    # 🟢 ATTIVI
    attivi_text = ""
    for name, d in attivi[:15]:
        attivi_text += f"🟢 {name} — {d} giorni fa\n"

    if not attivi_text:
        attivi_text = "Nessun membro attivo"

    embed.add_field(
        name="🟢 Membri attivi",
        value=attivi_text,
        inline=False
    )

    # 🔴 INATTIVI
    inattivi_text = ""
    for name, d in inattivi[:15]:
        if d == "Mai attivo":
            inattivi_text += f"🔴 {name} — Mai attivo\n"
        else:
            inattivi_text += f"🔴 {name} — {d} giorni fa\n"

    if not inattivi_text:
        inattivi_text = "Nessun membro inattivo"

    embed.add_field(
        name="🔴 Membri inattivi",
        value=inattivi_text,
        inline=False
    )

    embed.add_field(
        name="📈 Statistiche",
        value=f"""🟢 Attivi: {len(attivi)}
🔴 Inattivi: {len(inattivi)}
📊 Totale: {len(attivi) + len(inattivi)}""",
        inline=False
    )

    embed.set_footer(text="Sistema stabile: messaggi + reazioni + backup anti-errori")

    await ctx.send(embed=embed)


# =========================
# RUN
# =========================

import os
bot.run(os.getenv("TOKEN"))
