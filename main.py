from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
import json
import random
import asyncio
from rapidfuzz import fuzz

LEADERBOARD_FILE = "leaderboard.json"

def load_questions():
    with open("questions.json", "r") as f:
        data = json.load(f)
        print(f"Loaded", len(data), "questions.")
        return data

questions = load_questions()

current_question = None
current_answer = None
players = {}
game_active = False
current_round_questions = []
answered_correctly = []
answered_this_round = set()
quiz_channel_id = None
NUMBER_OF_QUESTIONS_PER_ROUND = 10
DELAY_BETWEEN_ROUNDS = 30
accepting_answers = False

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except:
            return {}
    return {}

def save_leaderboard(data):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(data, f, indent=2)

leaderboard_data = load_leaderboard()

async def send_embed(channel, message, title=None, color=0x3498db):
    embed = discord.Embed(description=message, color=color)
    if title:
        embed.title = title
    await channel.send(embed=embed)

# ✅ Extract category text (first line of the question)
def get_category_from_question(question_text):
    return question_text.split("\n")[0].strip()

# ✅ Show all 10 categories (duplicates allowed, matches question order)
def get_round_categories(questions_list):
    return [get_category_from_question(q["question"]) for q in questions_list]


@bot.event
async def on_ready():
    global quiz_channel_id
    print(f"Bot connected as {bot.user}!")

    guild = bot.guilds[0]

    for channel in guild.text_channels:
        perms = channel.permissions_for(guild.me)
        if perms.send_messages and perms.read_messages:
            quiz_channel_id = channel.id
            await start_new_round(guild)
            return


async def start_new_round(guild):
    global game_active, players, answered_correctly, answered_this_round, current_round_questions, accepting_answers

    if game_active:
        return

    game_active = True
    players = {m.display_name: 0 for m in guild.members if not m.bot}
    answered_correctly = []
    answered_this_round = set()
    accepting_answers = False

    current_round_questions = random.sample(questions, min(NUMBER_OF_QUESTIONS_PER_ROUND, len(questions)))

    channel = bot.get_channel(quiz_channel_id)

    categories = get_round_categories(current_round_questions)
    await send_embed(channel, "\n".join(categories), title="🎯 Next Round Preview")

    await send_embed(channel, f"New round about to begin... ⏱️ {len(current_round_questions)} new questions!", title="🧐 Quiz Starting!")
    await asyncio.sleep(7)

    for index, q in enumerate(current_round_questions, start=1):
        await ask_single_question(channel, index, q)
        await asyncio.sleep(7)

    await end_round(channel, guild)


async def ask_single_question(channel, index, q):
    global current_question, current_answer, answered_correctly, answered_this_round, accepting_answers, players

    current_question = q["question"]
    current_answer = q["answer"].lower()
    answered_correctly = []
    answered_this_round = set()
    accepting_answers = True

    await send_embed(channel, f"**Question {index}:**\n{current_question}")

    await asyncio.sleep(10)
    accepting_answers = False

    if not answered_correctly:
        await send_embed(channel, f"No one got it! Correct answer: **{current_answer.title()}**", title="⏰ Time's Up!")
    else:
        results = "\n".join(f"{i+1}. {p} (+{pts} pts)" for i, (p, pts) in enumerate(answered_correctly))
        await send_embed(channel, f"Correct answer: **{current_answer.title()}**\n\n{results}", title="✅ Results")

        # NEW: Show round scores after results
        # Sort players by current round points descending
        sorted_round_scores = sorted(players.items(), key=lambda x: x[1], reverse=True)
        round_scores_lines = [f"{i+1}. {name} (+{score})" for i, (name, score) in enumerate(sorted_round_scores)]
        await send_embed(channel, "\n".join(round_scores_lines), title="📊 Round Scores")



async def end_round(channel, guild):
    global game_active, leaderboard_data

    game_active = False

    max_score = max(players.values()) if players else 0
    winners = [p for p, s in players.items() if s == max_score] if max_score > 0 else []

    if winners:
        await send_embed(channel, f"Winner: {', '.join(winners)} ({max_score} points)", title="🏁 Round Over!")
    else:
        await send_embed(channel, "No winners this round.", title="🏁 Round Over!")

    for player, score in players.items():
        leaderboard_data[player] = leaderboard_data.get(player, 0) + score
    save_leaderboard(leaderboard_data)

    await show_leaderboard(channel)
    await send_embed(channel, f"Next round starts in {DELAY_BETWEEN_ROUNDS} seconds…", title="⏳ Waiting")
    await asyncio.sleep(DELAY_BETWEEN_ROUNDS)

    await start_new_round(guild)


async def show_leaderboard(channel, round_over=False):
    if not leaderboard_data:
        await send_embed(channel, "Nobody has scored yet.", title="Leaderboard")
        return
    sorted_scores = sorted(leaderboard_data.items(), key=lambda x: x[1], reverse=True)
    lines = [f"**{i+1}. {name} ({score} points)**" for i, (name, score) in enumerate(sorted_scores)]
    await send_embed(channel, "\n".join(lines), title="🏆 Leaderboard 🏆")


@bot.command()
async def leaderboard(ctx):
    await show_leaderboard(ctx.channel)


@bot.command()
async def endquiz(ctx):
    global game_active
    game_active = False
    await ctx.send("🛑 Quiz ended manually.")


@bot.event
async def on_message(message):
    global answered_correctly, accepting_answers, players

    await bot.process_commands(message)

    if (
        message.author.bot
        or not game_active
        or not accepting_answers
        or message.channel.id != quiz_channel_id
    ):
        return

    user_answer = message.content.strip().lower()
    match_score = fuzz.ratio(user_answer, current_answer)

    if match_score >= 85 and message.author.id not in answered_this_round and len(answered_correctly) < 3:
        answered_this_round.add(message.author.id)
        player = message.author.display_name
        points_awarded = [15, 10, 5][len(answered_correctly)]

        if player not in players:
            players[player] = 0

        players[player] += points_awarded
        answered_correctly.append((player, points_awarded))


load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
