import discord
from discord.ext import commands, tasks
import aiosqlite
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# =========================
# RENDER WEB SERVER FIX
# =========================

def run_web():
    port = int(os.environ.get("PORT", 10000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# =========================
# DISCORD BOT
# =========================

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
# DB FUNCTIONS
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
# EVENTS
# =========================

@bot.event
async def on_ready():
    await init_db()
    backup_scan.start()
    print(f"✅ Connecté en tant que {bot.user}")

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
# BACKUP SCAN
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
# COMMAND: RESCAN
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def rescan(ctx):
    await ctx.send("🔄 Scan en cours...")

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

    await ctx.send(f"✅ Scan terminé : {count} messages")

# =========================
# COMMAND: ANALYSE
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
        title="📊 Analyse activité serveur",
        description=f"Derniers {giorni} jours",
        color=discord.Color.blurple()
    )

    attivi_text = "\n".join(
        f"🟢 {name} — {d} jours"
        for name, d in attivi[:15]
    ) or "Aucun membre actif"

    inattivi_text = "\n".join(
        f"🔴 {name} — {d if d != 'Mai attivo' else 'Jamais actif'}"
        for name, d in inattivi[:15]
    ) or "Aucun membre inactif"

    embed.add_field(name="🟢 Actifs", value=attivi_text, inline=False)
    embed.add_field(name="🔴 Inactifs", value=inattivi_text, inline=False)

    embed.add_field(
        name="📈 Stats",
        value=f"🟢 {len(attivi)} actifs\n🔴 {len(inattivi)} inactifs",
        inline=False
    )

    await ctx.send(embed=embed)

# =========================
# AUTO RESTART (ANTI CRASH)
# =========================

TOKEN = os.getenv("TOKEN")

while True:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print("❌ Crash bot → restart dans 5 sec :", e)
        time.sleep(5)
