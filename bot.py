import nextcord
from nextcord.ext import commands
import os
from dotenv import load_dotenv
import sqlite3
import datetime

# Load Environment Variables
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
JOB_CHANNEL_ID = int(os.getenv('JOB_CHANNEL_ID'))
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID'))
ADMIN_ROLE_ID = int(os.getenv('ADMIN_ROLE_ID'))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))
LOGO_URL = os.getenv('LOGO_URL')

intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ====================== DATABASE SETUP ======================
conn = sqlite3.connect('swift_swap_jobs.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS jobs (
             order_id INTEGER PRIMARY KEY AUTOINCREMENT,
             message_id INTEGER,
             title TEXT,
             description TEXT,
             reward REAL,
             deposit REAL,
             posted_by INTEGER,
             claimed_by INTEGER,
             status TEXT DEFAULT 'Open',
             created_at TEXT,
             ticket_channel_id INTEGER)''')

c.execute('''CREATE TABLE IF NOT EXISTS users (
             user_id INTEGER PRIMARY KEY,
             deposit_balance REAL DEFAULT 0.0,
             jobs_completed INTEGER DEFAULT 0)''')
conn.commit()

# ====================== UTILS ======================
def parse_value(value: str) -> float:
    val = str(value).strip().upper().replace(",", "").replace("$", "")
    multiplier = 1.0
    if val.endswith('B'): multiplier = 1_000_000_000; val = val[:-1]
    elif val.endswith('M'): multiplier = 1_000_000; val = val[:-1]
    elif val.endswith('K'): multiplier = 1_000; val = val[:-1]
    try:
        return float(val) * multiplier
    except:
        raise ValueError("Invalid Format")

def get_user_deposit(user_id: int):
    c.execute("SELECT deposit_balance FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    if res: return res[0]
    c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    return 0.0

# ====================== VIEWS ======================
class TicketView(nextcord.ui.View):
    def __init__(self, order_id: int):
        super().__init__(timeout=None)
        self.order_id = order_id

    @nextcord.ui.button(label="Mark Completed", style=nextcord.ButtonStyle.green, emoji="✅")
    async def complete(self, button, interaction):
        if not interaction.user.guild_permissions.administrator and not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Managers only!", ephemeral=True)
        
        c.execute("UPDATE jobs SET status='Completed' WHERE order_id=?", (self.order_id,))
        c.execute("UPDATE users SET jobs_completed = jobs_completed + 1 WHERE user_id = (SELECT claimed_by FROM jobs WHERE order_id=?)", (self.order_id,))
        conn.commit()
        await interaction.response.send_message("🎉 Job Marked as Completed!")

class JobView(nextcord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

    @nextcord.ui.button(label="Claim Job", style=nextcord.ButtonStyle.green, emoji="🤝")
    async def claim(self, button, interaction):
        c.execute("SELECT order_id, deposit, title, status FROM jobs WHERE message_id=?", (self.message_id,))
        res = c.fetchone()
        if not res or res[3] != 'Open':
            return await interaction.response.send_message("❌ Job already taken or closed.", ephemeral=True)

        order_id, job_depo, title, _ = res
        user_depo = get_user_deposit(interaction.user.id)

        if user_depo < job_depo:
            return await interaction.response.send_message(f"❌ Deposit too low! Need: {job_depo:,.0f}", ephemeral=True)

        c.execute("UPDATE jobs SET claimed_by=?, status='Claimed' WHERE message_id=?", (interaction.user.id, self.message_id))
        conn.commit()

        # Update Embed
        embed = interaction.message.embeds[0]
        embed.title = "👷 Job Claimed"
        embed.color = nextcord.Color.green()
        embed.add_field(name="Worker", value=interaction.user.mention)
        button.disabled = True
        await interaction.message.edit(embed=embed, view=self)

        # Create Ticket
        category = interaction.guild.get_channel(TICKET_CATEGORY_ID)
        ticket = await category.create_text_channel(name=f"job-{order_id}-{interaction.user.name}")
        await ticket.set_permissions(interaction.user, read_messages=True, send_messages=True)
        
        c.execute("UPDATE jobs SET ticket_channel_id=? WHERE order_id=?", (ticket.id, order_id))
        conn.commit()

        ticket_embed = nextcord.Embed(title=f"Ticket for Job #{order_id}", description=f"**Task:** {title}\nWorker: {interaction.user.mention}", color=0x2ecc71)
        await ticket.send(embed=ticket_embed, view=TicketView(order_id))
        await interaction.response.send_message(f"✅ Job Secured! Ticket: {ticket.mention}", ephemeral=True)

# ====================== COMMANDS ======================
@bot.slash_command(name="postjob", description="Post a new OSRS order")
async def postjob(interaction: nextcord.Interaction, title: str, reward: str, deposit: str, description: str):
    if not interaction.user.guild_permissions.administrator and not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
        return await interaction.response.send_message("❌ Permission Denied.", ephemeral=True)

    r_val = parse_value(reward)
    d_val = parse_value(deposit)
    
    c.execute("INSERT INTO jobs (title, description, reward, deposit, posted_by) VALUES (?,?,?,?,?)", 
              (title, description, r_val, d_val, interaction.user.id))
    conn.commit()
    oid = c.lastrowid

    embed = nextcord.Embed(title="🚀 New Service Job Available", description=description, color=0xf39c12)
    embed.add_field(name="📌 Job ID", value=f"`#{oid}`", inline=True)
    embed.add_field(name="💰 Reward", value=reward, inline=True)
    embed.add_field(name="🔐 Req. Deposit", value=deposit, inline=True)
    if LOGO_URL: embed.set_thumbnail(url=LOGO_URL)
    embed.set_footer(text=f"Posted by {interaction.user.display_name}")

    channel = bot.get_channel(JOB_CHANNEL_ID)
    msg = await channel.send(embed=embed, view=JobView(0))
    c.execute("UPDATE jobs SET message_id=? WHERE order_id=?", (msg.id, oid))
    conn.commit()
    await msg.edit(view=JobView(msg.id))
    await interaction.response.send_message("✅ Job Posted!", ephemeral=True)

@bot.slash_command(name="setdeposit")
async def setdeposit(interaction: nextcord.Interaction, user: nextcord.Member, amount: str):
    if not interaction.user.guild_permissions.administrator: return
    val = parse_value(amount)
    c.execute("INSERT OR REPLACE INTO users (user_id, deposit_balance) VALUES (?,?)", (user.id, val))
    conn.commit()
    await interaction.response.send_message(f"✅ {user.name}'s deposit set to {val:,.0f}", ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(JobView(0))
    bot.add_view(TicketView(0))
    print(f"✅ Swift Swap Job Bot is Live: {bot.user}")

bot.run(TOKEN)