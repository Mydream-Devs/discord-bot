import os
import discord
from discord.ext import commands
from colorama import Fore, init
import logging
from discord.ext.commands import CheckFailure
import asyncio
from discord.ui import View, Button
import io
import time
import datetime
from datetime import timezone

init(autoreset=True)

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.CRITICAL)
discord_logger.disabled = True
logging.getLogger().setLevel(logging.CRITICAL)
logging.disable(logging.CRITICAL)

intents = discord.Intents.default()
intents.members = True  # ✅ Important
intents.message_content = True
intents.guilds = True
intents.messages = True 

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)
# Liste des rôles autorisés
ROLES_AUTORISES = [ "👑 • Owner", "👑• Co-Owner" ]
WARN_FILE = "warns.json"
# Enregistre l'heure de démarrage du bot
start_time = time.time()

@bot.event
async def on_ready():
    print(Fore.CYAN + f"                                                     {bot.user} Connecté")

# Vérification globale
@bot.check
async def global_role_check(ctx):
    return any(role.name in ROLES_AUTORISES for role in ctx.author.roles)

# Gestion des erreurs de permission
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CheckFailure):
        await ctx.send("❌ Tu n'as pas la permission d'utiliser ce bot.")
    else:
        raise error

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="𝓑𝓲𝓮𝓷𝓿𝓮𝓷𝓾𝓮")  # Remplace "general" par le nom du channel de bienvenue
    if channel:
        await channel.send(f"Bienvenue sur notre serveur, {member.mention} ! Si tu as besoin d'aide passe par https://discord.com/channels/1384895593775890524/1384895594643849231")

class CloseTicketButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild
        author = interaction.user

        if not channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ Ce n’est pas un salon de ticket.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Fermeture du ticket dans 5 secondes...", ephemeral=True)
        await asyncio.sleep(5)

        # Récupération des messages (tout l’historique)
        messages = []
        async for msg in channel.history(limit=None, oldest_first=True):
            time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author_name = msg.author.name
            content = msg.content
            messages.append(f"[{time_str}] {author_name}: {content}")

        transcript = "\n".join(messages)

        # Supprime le salon
        await channel.delete(reason=f"Ticket fermé par {author}")

        # Embed avec bouton pour le transcript
        class TranscriptView(View):
            def __init__(self, transcript_text):
                super().__init__(timeout=None)
                self.transcript_text = transcript_text

            @discord.ui.button(label="📄 Afficher le transcript", style=discord.ButtonStyle.primary)
            async def show_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
                chunks = [self.transcript_text[i:i+1900] for i in range(0, len(self.transcript_text), 1900)]
                for chunk in chunks:
                    await interaction.response.send_message(f"```{chunk}```", ephemeral=True)

            @discord.ui.button(label="⬇ Télécharger le transcript", style=discord.ButtonStyle.secondary)
            async def download_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
                file = discord.File(io.StringIO(self.transcript_text), filename="transcript.txt")
                await interaction.response.send_message("Voici votre transcript :", file=file, ephemeral=True)

        # Envoi dans le canal logs
        log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
        if log_channel:
            embed = discord.Embed(
                title="🔒 Ticket fermé",
                description=f"👤 Fermé par : {author.mention}\n📁 Salon : {channel.name}\n📝 Transcript disponible via les boutons ci-dessous.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed, view=TranscriptView(transcript))

class TicketButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.grey, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        author = interaction.user
        support_role = discord.utils.get(guild.roles, name="🧰 • Staff")

        existing = discord.utils.get(guild.text_channels, name=f"ticket-{author.name.lower()}")
        if existing:
            await interaction.response.send_message("❌ Tu as déjà un ticket ouvert.", ephemeral=True)
            return

        category_name = "🎟️ Tickets"
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            category = await guild.create_category(name=category_name, reason="Catégorie tickets auto-créée")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{author.name}",
            overwrites=overwrites,
            category=category,
            reason="Création d’un ticket via bouton"
        )

        # Envoie message avec bouton pour fermer
        await ticket_channel.send(
            f"🎟️ Ticket ouvert par {author.mention}. Un membre du staff va te répondre.",
            view=CloseTicketButton()
        )

        log_channel = discord.utils.get(guild.text_channels, name="logs")
        if log_channel:
            log_embed = discord.Embed(
                title="🎫 Ticket ouvert",
                description=(
                    f"👤 Utilisateur : {author.mention}\n"
                    f"🆔 ID : `{author.id}`\n"
                    f"📁 Salon : {ticket_channel.mention}"
                ),
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=log_embed)

        await interaction.response.send_message(f"✅ Ton ticket a été ouvert : {ticket_channel.mention}", ephemeral=True)

# Chargement des warnings depuis fichier
def load_warns():
    if not os.path.exists(WARN_FILE):
        return {}
    with open(WARN_FILE, "r") as f:
        return json.load(f)

# Sauvegarde des warnings
def save_warns(data):
    with open(WARN_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.command()
async def uptime(ctx):
    now = time.time()
    uptime_seconds = int(now - start_time)
    uptime_str = str(datetime.timedelta(seconds=uptime_seconds))

    embed = discord.Embed(
        title="⏱️ Uptime du bot",
        description=f"Le bot est en ligne depuis :\n`{uptime_str}`",
        color=discord.Color.green()
    )
    embed.set_footer(text="Dernier redémarrage")
    await ctx.send(embed=embed)

# ⚠️ +warn
@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="Aucune raison spécifiée."):
    warns = load_warns()
    uid = str(member.id)

    warn_data = {
        "moderator": str(ctx.author.id),
        "reason": reason,
        "timestamp": datetime.now().strftime("%d/%m/%Y à %H:%M")
    }

    if uid not in warns:
        warns[uid] = []

    warns[uid].append(warn_data)
    save_warns(warns)

    embed = discord.Embed(
        title="⚠️ Avertissement",
        description=f"{member.mention} a été averti.",
        color=discord.Color.orange()
    )
    embed.add_field(name="📄 Raison", value=reason, inline=False)
    embed.set_footer(text=f"Modérateur : {ctx.author} | ID : {member.id}")
    await ctx.send(embed=embed)

    try:
        await member.send(f"⚠️ Tu as été averti sur **{ctx.guild.name}**.\n**Raison :** {reason}")
    except:
        pass

# 📜 +warns
@bot.command()
@commands.has_permissions(manage_messages=True)
async def warns(ctx, member: discord.Member):
    warns = load_warns()
    uid = str(member.id)

    if uid not in warns or len(warns[uid]) == 0:
        return await ctx.send(f"✅ Aucun avertissement pour {member.mention}.")

    embed = discord.Embed(
        title=f"📋 Avertissements de {member}",
        color=discord.Color.gold()
    )

    for i, w in enumerate(warns[uid], 1):
        mod = await bot.fetch_user(int(w["moderator"]))
        embed.add_field(
            name=f"⚠️ Warn {i}",
            value=f"**Modérateur :** {mod.mention}\n**Raison :** {w['reason']}\n**Date :** {w['timestamp']}",
            inline=False
        )

    await ctx.send(embed=embed)

# ❌ +unwarn
@bot.command()
@commands.has_permissions(manage_messages=True)
async def unwarn(ctx, member: discord.Member, warn_number: int):
    warns = load_warns()
    uid = str(member.id)

    if uid not in warns or warn_number <= 0 or warn_number > len(warns[uid]):
        return await ctx.send("❌ Warn introuvable avec ce numéro.")

    removed = warns[uid].pop(warn_number - 1)
    save_warns(warns)

    embed = discord.Embed(
        title="🗑️ Avertissement supprimé",
        description=f"Avertissement {warn_number} supprimé pour {member.mention}.",
        color=discord.Color.green()
    )
    embed.add_field(name="Raison supprimée", value=removed["reason"], inline=False)
    await ctx.send(embed=embed)

# 🔥 +clearwarns
@bot.command()
@commands.has_permissions(manage_messages=True)
async def clearwarns(ctx, member: discord.Member):
    warns = load_warns()
    uid = str(member.id)

    if uid not in warns or not warns[uid]:
        return await ctx.send(f"✅ Aucun avertissement à supprimer pour {member.mention}.")

    count = len(warns[uid])
    warns[uid] = []
    save_warns(warns)

    await ctx.send(f"🧹 {count} avertissement(s) supprimé(s) pour {member.mention}.")

@bot.command()
async def say(ctx, *, message: str):
    await ctx.message.delete()  # Supprime le message d'origine
    await ctx.send(message)


@bot.command()
async def lookup(ctx, discord_id: int):
    embed = discord.Embed(color=discord.Color.blurple())
    found = False
    title_type = "Inconnu"

    try:
        user = await bot.fetch_user(discord_id)
        created_at = user.created_at.astimezone(timezone.utc).strftime('%d/%m/%Y à %H:%M:%S UTC')
        banner = user.banner.url if user.banner else "Aucune"
        accent_color = user.accent_color if user.accent_color else "Non défini"
        discrim = f"#{user.discriminator}" if user.discriminator else ""

        embed.title = "🔍 Résultat Lookup : Utilisateur"

        # Bloc : Informations générales
        embed.add_field(
            name="👤 Informations générales",
            value=(
                f"**Nom :** {user.name}\n"
                f"**Mention :** <@{user.id}>\n"
                f"**ID :** `{user.id}`\n"
                f"**Bot :** {'✅' if user.bot else '❌'}"
            ),
            inline=False
        )

        # Bloc : Compte
        embed.add_field(
            name="📅 Création & Profil",
            value=(
                f"**Créé le :** {created_at}\n"
            ),
            inline=False
        )

        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)

        # Bloc serveur (si membre)
        member = ctx.guild.get_member(discord_id)
        if member:
            joined_at = member.joined_at.astimezone(timezone.utc).strftime('%J/%M/%A à %H:%M:%S UTC')
            roles = ", ".join([role.mention for role in member.roles if role.name != "@everyone"]) or "Aucun"
            embed.add_field(
                name="🧩 Informations sur le serveur",
                value=(
                    f"**Pseudo serveur :** {member.nick or 'Cette personne à pas de pseudo de serveur.'}\n"
                    f"**Rejoint le :** {joined_at}\n"
                    f"**Statut :** {member.status}\n"
                    f"**Rôles :** {roles}"
                ),
                inline=False
            )
            if member.avatar and member.avatar != user.avatar:
                embed.set_image(url=member.avatar.url)

        found = True

    except Exception as e:
        print(f"[ERREUR FETCH USER] {e}")

    if not found:
        embed = discord.Embed(
            title="❌ Rien trouvé",
            description="Aucune ressource trouvée avec cette ID.",
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)

@bot.command()
async def pay(ctx):
    embed = discord.Embed(
        title="🛒 ***Voici Notre PayPal pour tout achat dans le Shop***",
        description=(
            "Merci à tous ceux qui achète nos services\n\n"
            "🎯 Chaque achat nous aide à améliorer le serveur.\n"
            "🔒 Paiement 100% sécurisé via PayPal."
        ),
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1384907908961144903/1395486885845143602/PayPal_Logo2014.png")
    embed.set_footer(text="Merci pour vos achats")

    button = Button(
        label="Faire un Achat via PayPal",
        url="https://www.paypal.me/Soku455",  # ← Remplace par ton vrai lien PayPal.me
        emoji="💸",
        style=discord.ButtonStyle.link
    )

    view = View()
    view.add_item(button)

    await ctx.message.delete()
    await ctx.send(embed=embed, view=view)

    
# COMMANDE pour envoyer le message avec bouton (à utiliser 1 fois dans un salon)
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    embed = discord.Embed(
        title="🎫 Ouvrir un ticket",
        description="Clique sur le bouton ci-dessous pour créer un ticket privé avec le staff.",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed, view=TicketButton())

@bot.command(name="dmall")
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message):
    await ctx.message.delete()
    await ctx.send("📨 Envoi des messages privés en cours...")

    compteur = 0
    erreurs = 0

    embed = discord.Embed(
        title="📢 Annonce !!",
        description=message,
        color=discord.Color.purple()
    )
    embed.set_footer(
        text=f"Envoyé par {ctx.author}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )

    for i, member in enumerate(ctx.guild.members):
        if member.bot:
            continue  # Ignore les bots

        try:
            await member.send(embed=embed)
            compteur += 1
        except discord.Forbidden:
            erreurs += 1  # MP désactivé
        except Exception:
            erreurs += 1  # Autre erreur

        await asyncio.sleep(2)  # ⏱️ Pause entre chaque DM

        # ⏳ Pause supplémentaire toutes les n personnes
        if compteur % 20 == 0:
            await asyncio.sleep(8)

    await ctx.send(f"✅ DMs envoyés à {compteur} membres.\n❌ Échec pour {erreurs} membres.")

@bot.command()
async def shop(ctx):
    embed = discord.Embed(
        title="🛒 Boutique Officielle",
        description="Découvrez tous nos services exclusifs !",
        color=discord.Color.purple()
    )
    embed.set_image(url="https://media.discordapp.net/attachments/xxx/shop_banner.png")
    embed.set_footer(text="Clique sur le bouton ci-dessous pour visiter le shop.")

    button = Button(label="Accéder au Shop", url="https://msmarket.mysellauth.com/", emoji="🛍️", style=discord.ButtonStyle.link)
    view = View()
    view.add_item(button)

    await ctx.send(embed=embed, view=view)

@bot.command()
async def embed(ctx, *, args):
    await ctx.message.delete()

    # Fonction simple pour parser les arguments sous forme clé=valeur
    def parse_args(text):
        parts = text.split()
        data = {}
        key = None
        value_parts = []
        for part in parts:
            if "=" in part:
                if key:
                    data[key] = " ".join(value_parts)
                key, val = part.split("=", 1)
                value_parts = [val]
            else:
                value_parts.append(part)
        if key:
            data[key] = " ".join(value_parts)
        return data

    data = parse_args(args)

    # Récupération des champs
    titre = data.get("titre", None)
    description = data.get("description", None)
    couleur = data.get("couleur", "blue").lower()
    footer = data.get("footer", None)

    # Conversion couleur simple
    couleurs = {
        "blue": discord.Color.blue(),
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "orange": discord.Color.orange(),
        "purple": discord.Color.purple(),
        "gold": discord.Color.gold(),
        "grey": discord.Color.light_grey()
    }
    color = couleurs.get(couleur, discord.Color.blue())

    embed = discord.Embed(color=color)

    if titre:
        embed.title = titre
    if description:
        embed.description = description
    if footer:
        embed.set_footer(text=footer)

    await ctx.send(embed=embed)

# Commande : +ping
@bot.command()
async def ping(ctx):
    latence = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong ! Latence : `{latence} ms`")

# Commande : +purge [nombre]
@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, nombre: int):
    if nombre < 1 or nombre > 100:
        await ctx.send("❌ Tu dois choisir un nombre entre 1 et 100.")
        return

    deleted = await ctx.channel.purge(limit=nombre + 1)
    confirmation = await ctx.send(f"✅ {len(deleted) - 1} messages supprimés.")
    await confirmation.delete(delay=5)

@purge.error
async def purge_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas la permission de supprimer les messages.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Utilisation : `+purge [nombre]`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Le nombre doit être un entier.")
    else:
        await ctx.send(f"❌ Erreur : {error}")

# Commande : +kick @membre [raison]
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, membre: discord.Member, *, raison=None):
    try:
        await membre.kick(reason=raison)
        await ctx.send(f"👢 {membre.mention} a été kické. Raison : {raison or 'Aucune'}")
    except discord.Forbidden:
        await ctx.send("❌ Je n’ai pas la permission de kick ce membre.")

# Commande : +ban @membre [raison]
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, membre: discord.Member, *, raison=None):
    try:
        await membre.ban(reason=raison)
        await ctx.send(f"🔨 {membre.mention} a été banni. Raison : {raison or 'Aucune'}")
    except discord.Forbidden:
        await ctx.send("❌ Je n’ai pas la permission de bannir ce membre.")

# Commande : +help
@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title=":milky_way: Aide - Commandes du Bot",
        description="Voici les commandes disponibles :",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="`+ping`",
        value="Affiche la latence du bot.",
        inline=False
    )

    embed.add_field(
        name="`+purge [nombre]`",
        value="Supprime un nombre de messages (1 à 100).",
        inline=False
    )

    embed.add_field(
        name="`+kick @membre [raison]`",
        value="Expulse un membre du serveur.",
        inline=False
    )

    embed.add_field(
        name="`+ban @membre [raison]`",
        value="Bannit un membre du serveur.",
        inline=False
    )

    embed.add_field(
        name="`+help`",
        value="Affiche le message d'aide.",
        inline=False
    )
    
    embed.add_field(
        name="`+dmall [message]`",
        value="Envoie un DM a toutes les personnes du serveur",
        inline=False
    )
    
    embed.add_field(
        name="`+say [message]`",
        value="Fait envoyer un message au bot",
        inline=False
    )
    
    embed.add_field(
        name="`+warn @membre [raison]`",
        value="Avertit le membre",
        inline=False
    )
    
    embed.add_field(
        name="`+warns @membre`",
        value="Liste tous ses warns d'un membre",
        inline=False
    )
    
    embed.add_field(
        name="`+clearwarns @membre`",
        value="Supprime tous les warns d'un membre",
        inline=False
    )
    
    embed.add_field(
        name="`+unwarn @membre 2`",
        value="Supprime le warn n°2",
        inline=False
    )
    
    embed.add_field(
        name="`+lookup [ID]`",
        value="permet de faire un lookup sur une personne",
        inline=False
    )
    
    embed.add_field(
        name="`+shop`",
        value="Crer un embed présentant le shop",
        inline=False
    )
    
    embed.add_field(
        name="`+pay`",
        value="Crer un embed pour qu'une personne paie",
        inline=False
    )
    
    embed.add_field(
        name="`+setup_ticket`",
        value="Permet de setup les tickets",
        inline=False
    )
    
    embed.add_field(
        name="`+uptime`",
        value="Montre le temp de connexion du bot",
        inline=False
    )
    
    embed.add_field(
        name="`+embed`",
        value=(
            "   Crée un message embed personnalisé avec plusieurs options :\n"
            """
                """
            "   **Exemple :**\n"
            "   +embed titre=Salut description=Voici un message couleur=red footer=Bot par Malone"
            "   Vous pouvez tout de meme retirer des options si il le faut."
    ),
    inline=False
)

    await ctx.send(embed=embed)

os.system('cls' if os.name == 'nt' else 'clear')
print("\n" * 1)

print(Fore.RED + "                                              +===============================+")
print(Fore.RED + "                                              + Bot Discord lancé avec succès +")
print(Fore.RED + "                                              +===============================+")

bot.run("MTM4NTc0NzMxMjczODgyODQ1OA.GO8H_d.owvv3mb2WKOofA9JcbEhzJGZJc73NLVQxearCY")