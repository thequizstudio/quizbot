from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
import json
import random
import asyncio
from rapidfuzz import fuzz

LEADERBOARD_FILE = "leaderboard.json"

# Load questions from JSON
def load_questions():
    with open("questions.json", "r") as f:
        data = json.load(f)
        print(f"Loaded {len(data)} questions.")
        return data

questions = load_questions()

current_question = None
current_answer = None
players = {}  # Current round points, reset each round
game_active = False
current_round_questions = []
current_question_index = 0
answered_correctly = False
answered_this_round = set()
quiz_channel_id = None  # Store the ID of the channel where the quiz is running
NUMBER_OF_QUESTIONS_PER_ROUND = 3  # Adjust as needed
DELAY_BETWEEN_ROUNDS = 10  # Seconds
accepting_answers = False  # New global flag

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Helper functions to manage persistent leaderboard ---

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    print("Leaderboard file is not a dictionary, resetting.")
                    return {}
                return data
        except json.JSONDecodeError:
            print("Leaderboard JSON decode error, resetting leaderboard.")
            return {}
        except Exception as e:
            print(f"Unexpected error loading leaderboard: {e}")
            return {}
    return {}

def save_leaderboard(data):
    try:
        with open(LEADERBOARD_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print("Leaderboard saved successfully.")
    except Exception as e:
        print(f"Error saving leaderboard: {e}")

leaderboard_data = load_leaderboard()  # Persistent total wins/scores

# --- Bot events and commands ---

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
            perms = channel.permissions_for(guild.me)
            print(f"Checking channel: {channel.name} ({channel.id}) - Permissions: Send Messages={perms.send_messages}, Read Messages={perms.read_messages}")
            if perms.send_messages and perms.read_messages:
                global quiz_channel_id
                quiz_channel_id = channel.id
                print(f"Quiz will run in channel: {channel.name} ({channel.id})")
                await start_new_round(guild)
                return
        print("Error: Could not find a suitable channel to run the quiz in.")
    else:
        print("Error: Bot is not in any guilds.")

async def start_new_round(guild):
    global game_active, current_question, current_answer, current_round_questions, current_question_index, players, answered_this_round, accepting_answers

    if game_active:
        print("A quiz is already running, but a new round was triggered.")
        return

    print(f"Starting new round in guild: {guild.name}")
    game_active = True
    players.clear()
    answered_this_round.clear()
    current_question_index = 0
    current_round_questions = random.sample(questions, min(NUMBER_OF_QUESTIONS_PER_ROUND, len(questions)))
    accepting_answers = False  # Initialize to False at the start of a round

    # Automatically enroll all non-bot members present at the start
    for member in guild.members:
        if not member.bot:
            players[member.name] = 0

    if quiz_channel_id:
        channel = bot.get_channel(quiz_channel_id)
        if channel:
            permissions = channel.permissions_for(channel.guild.me)
            if not permissions.send_messages or not permissions.read_messages:
                print(f"Missing permissions to send/read messages in channel {channel.name}")
                await channel.send("⚠️ I don't have permission to send or read messages in this channel. Please update my permissions.")
                game_active = False
                return

            await channel.send(f"🎉 New quiz round starting! {len(current_round_questions)} questions ahead!")
            await ask_next_question(channel)
        else:
            print(f"Error: Could not find channel with ID {quiz_channel_id}")
            game_active = False
    else:
        print("Error: quiz_channel_id is not set.")
        game_active = False

async def ask_next_question(channel):
    global current_question, current_answer, current_question_index, answered_correctly, game_active, answered_this_round, accepting_answers

    if not game_active:
        return

    if current_question_index >= len(current_round_questions):
        # Round is over - immediately mark game as inactive
        global game_active
        game_active = False

        await channel.send("🏁 Round over!")
        print("Round over: showing leaderboard now...")
        await show_leaderboard(channel, round_over=True)
        print("Leaderboard shown, waiting to start next round...")
        await channel.send(f"Next round starting in {DELAY_BETWEEN_ROUNDS} seconds... Get ready!")

        await asyncio.sleep(DELAY_BETWEEN_ROUNDS)

        restarted = False
        for guild in bot.guilds:
            if guild.get_channel(channel.id):
                try:
                    await start_new_round(guild)
                    restarted = True
                    break
                except Exception as e:
                    print(f"Error starting new round in guild {guild.name}: {e}")

        if not restarted:
            await channel.send("⚠️ Error: Could not find guild with the quiz channel to start new round.")
        return

    # Ask the next question
    q = current_round_questions[current_question_index]
    current_question = q["question"]
    current_answer = q["answer"].lower()
    answered_correctly = False
    answered_this_round = set()
    accepting_answers = True  # Start accepting answers for the new question

    current_question_index += 1

    permissions = channel.permissions_for(channel.guild.me)
    print(f"Bot has Send Messages permission in #{channel.name}: {permissions.send_messages}")
    print(f"Bot has View Channel permission in #{channel.name}: {permissions.view_channel}")

    await channel.send(f"❓ Question {current_question_index}:\n**{current_question}**")

    try:
        await asyncio.sleep(10)  # Wait for answers
        accepting_answers = False  # Stop accepting answers after time is up
        if not answered_correctly:
            await channel.send(f"⏰ Time's up! The correct answer was: **{current_answer}**")
        await asyncio.sleep(7)  # Short delay before the next question
        if game_active:
            await ask_next_question(channel)
    except Exception as e:
        print("Error during question timing:", e)

async def show_leaderboard(channel, round_over=False):
    global leaderboard_data

    if round_over:
        # Add current round points to persistent leaderboard safely
        try:
            for player, score in players.items():
                leaderboard_data[player] = leaderboard_data.get(player, 0) + score
            save_leaderboard(leaderboard_data)
        except Exception as e:
            print(f"Error updating leaderboard after round: {e}")

    if not leaderboard_data:
        await channel.send("Nobody scored anything so far! 💀")
        return

    sorted_scores = sorted(leaderboard_data.items(), key=lambda x: x[1], reverse=True)
    leaderboard_lines = []
    for i, (name, score) in enumerate(sorted_scores, start=1):
        leaderboard_lines.append(f"**{i}. {name}** - {score} points")

    title = "🏆 **All-Time Leaderboard**" if not round_over else "🏆 **Leaderboard after this round:**"
    await channel.send(f"{title}\n" + "\n".join(leaderboard_lines))

@bot.command()
async def leaderboard(ctx):
    await show_leaderboard(ctx.channel)

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
    global current_question, current_answer, answered_correctly, game_active, answered_this_round, accepting_answers

    await bot.process_commands(message)

    if message.author.bot or not game_active or not current_question or message.channel.id != quiz_channel_id or not accepting_answers:
        return

    user_answer = message.content.strip()
    match_score = fuzz.ratio(user_answer.lower(), current_answer)

    if match_score >= 85 and not answered_correctly and message.author.id not in answered_this_round:
        answered_correctly = True
        answered_this_round.add(message.author.id)
        player = message.author.name
        players[player] = players.get(player, 0) + 15
        await message.channel.send(
            f"⚡ Fastest Finger! ✅ Correct, {player}! +15 points 🎉 (Total this round: {players[player]} points)"
        )
        return

    if game_active and message.author.name not in players and not message.author.bot:
        players[message.author.name] = players.get(message.author.name, 0)

# Start the bot
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
