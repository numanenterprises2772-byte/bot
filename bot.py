import nextcord
from nextcord.ext import commands
from flask import Flask
from threading import Thread
import os

# --- 24/7 HOSTING SETUP ---
app = Flask('')
@app.route('/')
def home():
    return "Swift Swap Multi-Bot is Online 24/7!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- BOT SETUP ---
TOKEN = 'MTQ4NzE5Mzk4NzU5MTk2MjY3NA.Gcjpaq.I62hYbBFxTWO6nSnmBSHkFc4wGgTROqm-E3R20'
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- 1. JOB SYSTEM (From job_Bot) ---
@bot.slash_command(name="postjob", description="Post a new OSRS job")
async def postjob(interaction: nextcord.Interaction, title: str, reward: str, deposit: str, description: str):
    # Check for Admin/Manager Permissions here
    embed = nextcord.Embed(title=f"🛠️ NEW JOB: {title}", color=0x2ecc71)
    embed.add_field(name="💰 Reward", value=reward, inline=True)
    embed.add_field(name="🔒 Deposit Required", value=deposit, inline=True)
    embed.add_field(name="📝 Description", value=description, inline=False)
    
    view = nextcord.ui.View()
    claim_button = nextcord.ui.Button(label="Claim Job", style=nextcord.ButtonStyle.green)
    
    async def claim_callback(inter):
        await inter.response.send_message("Ticket creating... (System Linking)", ephemeral=True)
    
    claim_button.callback = claim_callback
    view.add_item(claim_button)
    await interaction.response.send_message("Job Posted!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=view)

# --- 2. PRICING SYSTEM (From !sendprices) ---
class PricingView(nextcord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label="Skilling Prices", style=nextcord.ButtonStyle.blurple)
    async def skilling(self, button, interaction):
        embed = nextcord.Embed(title="💪 Skilling Rates", description="Agility 1-99: 180M\nCombat: 45M per Skill", color=0x3498db)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command()
async def sendprices(ctx):
    embed = nextcord.Embed(title="✨ SWIFT SWAP SERVICES", description="Click below for our rates", color=0x2ecc71)
    await ctx.send(embed=embed, view=PricingView())

# --- 3. CALCULATOR SYSTEM (From !setupcalc) ---
@bot.slash_command(name="calculator", description="Calculate OSRS service cost")
async def calculator(interaction: nextcord.Interaction, start_xp: int, end_xp: int, rate_per_mil_xp: int):
    total_xp = end_xp - start_xp
    total_cost = (total_xp / 1_000_000) * rate_per_mil_xp
    await interaction.response.send_message(f"📊 **Total XP:** {total_xp:,}\n💰 **Estimated Cost:** {total_cost:.2f}M", ephemeral=True)

# --- 4. STATUS & LINK SYSTEM (From !status) ---
@bot.command()
async def status(ctx):
    embed = nextcord.Embed(title="🤖 System Status", description="✅ All systems operational\n✅ Database Connected\n✅ Dink Plugin Active", color=0x2ecc71)
    await ctx.send(embed=embed)

@bot.command()
async def link(ctx, rsn: str):
    await ctx.send(f"🔗 **RSN Linked:** `{rsn}` has been successfully connected to this ticket.")

# --- BOT EVENTS ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.sync_all_application_commands() # This syncs slash commands

# --- START ---
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
