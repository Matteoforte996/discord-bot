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
    attivi_text = "\n".join(
        f"🟢 {name} — {d} giorni fa"
        for name, d in attivi[:15]
    ) or "Nessun membro attivo"

    # 🔴 INATTIVI
    inattivi_text = "\n".join(
        f"🔴 {name} — {'Mai attivo' if d == 'Mai attivo' else f'{d} giorni fa'}"
        for name, d in inattivi[:15]
    ) or "Nessun membro inattivo"

    embed.add_field(name="🟢 Membri attivi", value=attivi_text, inline=False)
    embed.add_field(name="🔴 Membri inattivi", value=inattivi_text, inline=False)

    # 📊 STATISTICHE FIXES (comme demandé)
    embed.add_field(
        name="📈 Statistiche",
        value="🟢 Attivi: 17\n🔴 Inattivi: 6",
        inline=False
    )

    embed.set_footer(text="Sistema stabile: messaggi + reazioni + backup anti-errori")

    await ctx.send(embed=embed)
