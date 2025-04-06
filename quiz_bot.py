from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
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
game_active = False
current_round_questions = []
current_question_index = 0
answered_correctly = False
answered_this_round = set()
quiz_channel_id = None  # Store the ID of the channel where the quiz is running
NUMBER_OF_QUESTIONS_PER_ROUND = 5  # Adjust as needed
DELAY_BETWEEN_ROUNDS = 15  # Seconds

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("on_ready event triggered!")
    while not bot.guilds:
        print("Waiting for guilds to become available...")
        await asyncio.sleep(1)  # Wait for 1 second

    print(f"Number of guilds connected: {len(bot.guilds)}")
    if bot.guilds:
        guild = bot.guilds[0]
        print(f"First guild: {guild.name} ({guild.id})")
        for channel in guild.text_channels:
            print(f"Checking channel: {channel.name} ({channel.id}) - Permissions: Send Messages={channel.permissions_for(guild.me).send_messages}, Read Messages={channel.permissions_for(guild.me).read_messages}")
            if channel.permissions_for(guild.me).send_messages and channel.permissions_for(guild.me).read_messages:
                global quiz_channel_id
                quiz_channel_id = channel.id
                print(f"Quiz will run in channel: {channel.name} ({channel.id})")
                await start_new_round(guild)
                return
        print("Error: Could not find a suitable channel to run the quiz in.")
    else:
        print("Error: Bot is not in any guilds.")

async def start_new_round(guild):
    global game_active, current_question, current_answer, current_round_questions, current_question_index, players, answered_this_round

    if game_active:
        print("A quiz is already running, but a new round was triggered.")
        return

    game_active = True
    players.clear()
    answered_this_round.clear()
    current_question_index = 0
    current_round_questions = random.sample(questions, min(NUMBER_OF_QUESTIONS_PER_ROUND, len(questions)))

    # Automatically enroll all non-bot members present at the start
    for member in guild.members:
        if not member.bot:
            players[member.name] = 0

    if quiz_channel_id:
        channel = bot.get_channel(quiz_channel_id)
        if channel:
            await channel.send(f"🎉 New quiz round starting! {len(current_round_questions)} questions ahead!")
            await ask_next_question(channel)
        else:
            print(f"Error: Could not find channel with ID {quiz_channel_id}")
            game_active = False
    else:
        print("Error: quiz_channel_id is not set.")
        game_active = False

async def ask_next_question(channel):
    global current_question, current_answer, current_question_index, answered_correctly, game_active, answered_this_round

    if not game_active:
        return

    if current_question_index >= len(current_round_questions):
        game_active = False
        await channel.send("🏁 Round over!")
        await show_leaderboard(channel)
        await asyncio.sleep(DELAY_BETWEEN_ROUNDS)
        # Find the guild the channel belongs to
        for guild in bot.guilds:
            if guild.get_channel(channel.id):
                await start_new_round(guild)
                break
        return

    q = current_round_questions[current_question_index]
    current_question = q["question"]
    current_answer = q["answer"].lower()
    answered_correctly = False
    answered_this_round = set() # Reset for the new question

    current_question_index += 1
    await channel.send(f"❓ Question {current_question_index}:\n**{current_question}**")

    try:
        await asyncio.sleep(10)  # Wait for answers
        if not answered_correctly:
            await channel.send(f"⏰ Time's up! The correct answer was: **{current_answer}**")
        await asyncio.sleep(5)  # Short delay before the next question
        if game_active: # Check if the game is still active before asking the next question
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
    await channel.send(f"🏆 Round Leaderboard:\n{leaderboard_text}")

@bot.command()
async def endquiz(ctx):
    global game_active
    if not game_active:
        await ctx.send("No quiz is running.")
        return

    game_active = False
    await ctx.send("🛑 Quiz ended.")

@bot.event
async def on_message(message):
    global current_question, current_answer, answered_correctly, game_active, answered_this_round

    await bot.process_commands(message)

    if message.author.bot or not game_active or not current_question or message.channel.id != quiz_channel_id:
        return

    user_answer = message.content.strip()
    match_score = fuzz.ratio(user_answer.lower(), current_answer)

    if match_score >= 85 and not answered_correctly and message.author.id not in answered_this_round:
        answered_correctly = True
        answered_this_round.add(message.author.id)
        player = message.author.name
        players[player] = players.get(player, 0) + 15  # 10 base + 5 fastest finger
        await message.channel.send(
            f"⚡ Fastest Finger! ✅ Correct, {player}! +15 points 🎉 (Total: {players[player]} points)"
        )
        return # Important: Exit after a correct answer

    # If the user is not yet in the players list, add them (for potential future correct answers in the same round)
    if game_active and message.author.name not in players and not message.author.bot:
        players[message.author.name] = players.get(message.author.name, 0)

# Start the bot
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))