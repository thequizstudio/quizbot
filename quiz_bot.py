from dotenv import load_dotenv
import os
import discord
from discord.ext import commands, tasks
import json
import random
import asyncio
from rapidfuzz import fuzz

# Load questions from JSON
def load_questions():
    with open("questions.json", "r") as f:
        data = json.load(f)
        print(f"Loaded {len(data)} questions.")
        return data

questions = load_questions()
current_question = None
current_answer = None
players = {}
joined_players = set()
game_active = False
current_round_questions = []
current_question_index = 0
answered_correctly = False

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Allows the bot to track new member joins
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Quiz bot is online as {bot.user}!")
    auto_start_quiz.start()  # Start auto-starting the quiz when the bot is ready

@bot.event
async def on_member_join(member):
    # Automatically enroll the user when they join the server
    joined_players.add(member.id)
    print(f"{member.name} has been auto-enrolled in the quiz!")

@bot.command()
async def joinquiz(ctx):
    joined_players.add(ctx.author.id)
    await ctx.send(f"{ctx.author.name} has joined the quiz!")

@bot.command()
async def leavequiz(ctx):
    joined_players.discard(ctx.author.id)
    await ctx.send(f"{ctx.author.name} has left the quiz.")

@bot.command()
async def startquiz(ctx):
    global game_active, current_question, current_answer, current_round_questions, current_question_index

    if game_active:
        await ctx.send("A quiz is already running!")
        return

    if not joined_players:
        await ctx.send("No players have joined yet! Use `!joinquiz` to join.")
        return

    game_active = True
    players.clear()
    current_question_index = 0
    current_round_questions = random.sample(questions, 10)

    await ctx.send("🧠 Quiz started! 10 questions coming up!")
    await ask_next_question(ctx.channel)

async def ask_next_question(channel):
    global current_question, current_answer, current_question_index, answered_correctly, game_active

    if current_question_index >= 10:
        game_active = False
        await channel.send("🎉 Quiz over!")
        await show_leaderboard(channel)
        return

    q = current_round_questions[current_question_index]
    current_question = q["question"]
    current_answer = q["answer"].lower()
    answered_correctly = False

    current_question_index += 1
    await channel.send(f"❓ Question {current_question_index}:\n**{current_question}**")

    try:
        await asyncio.sleep(10)  # Wait for 10 seconds for answers
        if not answered_correctly:
            await channel.send(f"⏰ Time's up! The correct answer was: **{current_answer}**")
        await asyncio.sleep(6)  # Wait before next question
        await ask_next_question(channel)
    except Exception as e:
        print("Error during question timing:", e)

@bot.command()
async def leaderboard(ctx):
    await show_leaderboard(ctx.channel)

async def show_leaderboard(channel):
    if not players:
        await channel.send("No scores yet.")
        return

    sorted_scores = sorted(players.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "\n".join([f"{name}: {score}" for name, score in sorted_scores])
    await channel.send(f"🏆 Final Leaderboard:\n{leaderboard_text}")

@bot.command()
async def endquiz(ctx):
    global game_active
    if not game_active:
        await ctx.send("No quiz is running.")
        return

    game_active = False
    await ctx.send("🛑 Quiz ended. Thanks for playing!")

@bot.event
async def on_message(message):
    global current_question, current_answer, answered_correctly

    await bot.process_commands(message)

    if message.author.bot or not game_active or not current_question:
        return

    if message.author.id not in joined_players:
        return

    user_answer = message.content.strip()
    match_score = fuzz.ratio(user_answer.lower(), current_answer)

    if match_score >= 85 and not answered_correctly:
        answered_correctly = True
        player = message.author.name
        players[player] = players.get(player, 0) + 15  # 10 base + 5 fastest finger
        await message.channel.send(
            f"⚡ Fastest Finger! ✅ Correct, {player}! +15 points 🎉 (Total: {players[player]} points)"
        )

# Auto-start quiz every time after 60 seconds (after quiz ends)
@tasks.loop(seconds=60)
async def auto_start_quiz():
    if not game_active:
        # Automatically start the quiz in a specific channel
        channel = bot.get_channel(YOUR_CHANNEL_ID_HERE)  # Replace with your channel ID
        await startquiz(channel)

# Start the bot
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
