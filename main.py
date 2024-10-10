import logging
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime
from typing import Final
from telegram.constants import ParseMode
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, Updater

load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_API_TOKEN")
#PORT = int(os.environ.get('PORT', '5000'))
#WEBHOOK = f"https://telemd.onrender.com/{TELEGRAM_TOKEN}"

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a structure for the questions based on the ALDEN criteria
questions = [
    # 1. Delay from initial drug component intake to onset of reaction
    {
        'text': 'Delay from initial drug component intake to onset of reaction?',
        'full_options': [
            'Suggestive: 5 to 28 days\n', 
            'Compatible: 29 to 56 days\n', 
            'Likely: 1 to 4 days\n', 
            'Unlikely: > 56 days\n', 
            'Excluded: Drug started on or after index day'
            ],
        'options': [
            'Suggestive +3', 
            'Compatible +2', 
            'Likely +1', 
            'Unlikely -1', 
            'Excluded -3'
            ],
        'scores': {
            'Suggestive +3': 3, 
            'Compatible +2': 2, 
            'Likely +1': 1, 
            'Unlikely -1': -1, 
            'Excluded -3': -3
            }
    },
    
    # 2. Drug present in the body on index day
    {
        'text': 'Was the drug present in the body on the index day?',
        'full_options': [
            'Definite: Drug continued up to index day or stopped at < 5x the elimination half-life before index day\n', 
            'Doubtful: Drug stopped at a time point before the index day by > 5x the elimination half-life but liver or kidney function alterations or suspected drug interactions\n', 
            'Excluded: Drug stopped at a time point before the index day by > 5x the elimination half-life but WITHOUT liver or kidney function alterations or suspected drug interactions\n'
        ],
        'options': [
            'Definite 0',
            'Doubtful -1',
            'Excluded -3'
        ],
        'scores': {
            'Definite 0': 0,
            'Doubtful -1': +1,
            'Excluded -3': -3
        }
    },

    # 3. Prechallenge/rechallenge
    {
        'text': 'Was there a prechallenge or rechallenge?',
        'full_options': [
            'Positive specific for disease AND drug: SJS/TEN after use of same drug\n', 
            'Positive specific for disease OR drug: SJS/TEN after use of similar drug or other reaction with same drug\n', 
            'Positive Unspecific: Other reaction after use of similar drug\n', 
            'Not done/Unknown: No known previous exposure\n', 
            'Negative: Drug exposure without reaction (before or after reaction)'
        ],
        'options': [
            'Positive specific for disease AND drug +4',
            'Positive specific for disease OR drug +2',
            'Positive Unspecific +1',
            'Not done/Unknown 0',
            'Negative -2'
        ],

        'scores': {
            'Positive specific for disease AND drug +4': 4,
            'Positive specific for disease OR drug +2': 2,
            'Positive Unspecific +1': 1,
            'Not done/Unknown 0': 0,
            'Negative -2': -2
        }
    },

    # 4. Dechallenge
    {
        'text': 'Did dechallenge occur (drug stopped)?',
        'full_options': [
            'Neutral: Drug stopped (or unknown)\n', 
            'Negative: Drug continued without harm'
        ],
        'options': [
            'Neutral 0',
            'Negative -2'
        ],

        'scores': {
            'Neutral 0': 0,
            'Negative -2': -2
        }
    },

    # 5. Type of drug (notoriety)
    {
        'text': 'Type of drug (notoriety)?',
        'full_options': [
            'Strongly associated: Drug of high-risk list according to previous studies\n', 
            'Associated: Drug with definite but lower risks according to previous studies\n', 
            'Suspected: Several previous reports, ambiguous epidemiology results (drug "under surveillance")\n', 
            'Unknown: All other drugs (including newly released)\n', 
            'Not suspected: No evidence of association from previous study with sufficient no. of exposed controls'
        ],
        'options': [
            'Strongly associated +3',
            'Associated +2',
            'Suspected +1',
            'Unknown 0',
            'Not suspected -1'
        ],
        'scores': {
            'Strongly associated +3': 3,
            'Associated +2': 2,
            'Suspected +1': 1,
            'Unknown 0': 0,
            'Not suspected -1': -1
        }
    },

    # 6. Other cause
    {
        'text': 'Is there another likely cause?',
        'full_options': [
            'Possible: Rank all drugs from highest to lowest immediate score. \nIf at least one has an intermediate score >3, subtract 1 from the score of each of the other drugs taken by the patient (another cause is more likely)\n', 
            'NA'
        ],
        'options': [
            "Possible -1",
            "NA 0"
        ],
        'scores': {
            'Possible -1': -1, 
            'NA 0': 0
        }
    }
]

# To store patient data
patient_data = {}  # Structure: {user_id: {patient_id: {score, timestamp}}}

# Function to start the ALDEN questionnaire by asking for Patient ID
async def alden(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Ask for Patient ID before starting the questions
    await update.message.reply_text("Please enter the Patient ID to begin (Initials, No., etc.)")
    context.user_data['awaiting_patient_id'] = True  # Flag to track Patient ID input

# Function to handle patient ID and questionnaire responses
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_input = update.message.text  # Get the user's input

    # Check if we're awaiting Patient ID
    if context.user_data.get('awaiting_patient_id'):
        '''if user_input in context.user_data['patient_id']:
            await update.message.reply_text(f"Patient ID {user_input} was already saved.")        
            await patient_confirm(update, context)
            context.user_data['patient_confirm'] = user_input
            if context.user_data['patient_confirm'] == "Overwrite":
                context.user_data['patient_id'] = user_input  # Store the Patient ID
                await update.message.reply_text(f"Patient ID {user_input} saved. Now starting the ALDEN questionnaire.")
            elif context.user_data['patient_confirm'] == "Change Patient ID":
                await update.message.reply_text("Please enter the Patient ID to begin (Initials, No., etc.)")
        else:''' 
        context.user_data['patient_id'] = user_input  # Store the Patient ID
        await update.message.reply_text(f"Patient ID {user_input} saved. Now starting the ALDEN questionnaire.")
        context.user_data['awaiting_patient_id'] = False  # Reset the flag
        
        # Initialize question index and score for the user
        context.user_data['question_index'] = 0
        context.user_data['score'] = 0  # Initialize score
        
        # Ask the first question
        await send_question(update, context, 0)
    elif context.user_data.get('alden'):
        # Proceed with handling ALDEN questions
        await handle_alden_question(update, context)
    else:
        if user_input.lower() not in ['/start','/restart', '/alden', '/history']:
            await suggest(update,context)

async def patient_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = ["Overwrite", "Change Patient ID"]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    await update.message.reply_text("Select action:", reply_markup=reply_markup)

# Function to ask a question
async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question_index: int) -> None:
    context.user_data['alden'] = True  # Flag to track alden question
    question = questions[question_index]
    full_options_text = "\n".join(question['full_options'])
    
    # Display the question and full options
    await update.message.reply_text(f"{question['text']}\n\n{full_options_text}")
    
    # Create a keyboard with options
    keyboard = [[option] for option in question['options']] + [["Previous"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text("Select your answer:", reply_markup=reply_markup)

# Function to handle each ALDEN question and calculate score
async def handle_alden_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_answer = update.message.text  # Get the user's answer
    user_id = update.message.from_user.id

    # Check if they selected "Previous"
    if user_answer == "Previous" and context.user_data['question_index'] > 0:
        context.user_data['question_index'] -= 1
        await send_question(update, context, context.user_data['question_index'])
        return

    # Get the current question index
    question_index = context.user_data.get('question_index', 0)
    
    # Get the corresponding question and score the answer
    question = questions[question_index]
    if user_answer not in question['options']:
        error_message = "Invalid input. Please select one of the provided options."
        await update.message.reply_text(error_message)
        await send_question(update, context, question_index)
        return
    
    context.user_data['score'] += question['scores'][user_answer]
        
    # Move to the next question if there are more
    if question_index + 1 < len(questions):
        context.user_data['question_index'] += 1
        await send_question(update, context, context.user_data['question_index'])
    else:
        # If no more questions, calculate and display the final score
        final_score = context.user_data['score']
        patient_id = context.user_data['patient_id']
        
        # Store the ALDEN score for the patient
        await store_alden_score(user_id, patient_id, final_score)
        
        await update.message.reply_text(f"Final ALDEN score for Patient ID {patient_id}: {final_score}")
        context.user_data.clear()  # Clear user data after the questionnaire is done
        context.user_data['alden'] = False  # Flag to track alden question
        await restart(update, context)

# Function to store ALDEN score
async def store_alden_score(user_id, patient_id, score):
    # Get current timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Initialize data for the user if not present
    if user_id not in patient_data:
        patient_data[user_id] = {}

    # Store the score with timestamp under the user's patient data
    patient_data[user_id][patient_id] = {
        'score': score,
        'timestamp': timestamp
    }

# Function to retrieve and display previous ALDEN scores
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    # Only retrieve patient data for the current user
    history_entries = [
        f"Patient ID: {pid}, Score: {data.get('score', 'N/A')}, Timestamp: {data.get('timestamp', 'N/A')}"
        for pid, data in patient_data.get(user_id, {}).items()  # Retrieve patient data for the current doctor
    ]

    if history_entries:
        history_message = "\n".join(history_entries)
        await update.message.reply_text(f"Here are your previous ALDEN scores:\n\n{history_message}")
    else:
        await update.message.reply_text("No previous ALDEN scores found.")


# Function to handle start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(text=f'Hello and welcome to TeleMD, {user.mention_markdown_v2()}\!\n\n'
                                    f"Please choose one of the available options:\n"
                                    f"\/start Show this menu\n"
                                    f"\/alden Start the ALDEN questionnaire\n"
                                    f"\/history View previous ALDEN scores\n",
                                    parse_mode=ParseMode.MARKDOWN_V2)

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(text=f'Thank you for using TeleMD \U0001f600 \n\n'
                                    f"If you'd like to continue, please choose one of the available options:\n"
                                    f"\/start Show this menu\n"
                                    f"\/alden Start the ALDEN questionnaire\n"
                                    f"\/history View previous ALDEN scores\n",
                                    parse_mode=ParseMode.MARKDOWN_V2)

async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(text=f"Sorry, I'm just a hard\-coded bot and can't answer your question :\(\n\n"
                                    f"Please suggest any improvements to @capsizin, or if you'd like to continue, choose one of the available options:\n"
                                    f"\/start Show this menu\n"
                                    f"\/alden Start the ALDEN questionnaire\n"
                                    f"\/history View previous ALDEN scores\n",
                                    parse_mode=ParseMode.MARKDOWN_V2)

# Function to handle errors
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f'Update {update} caused error {context.error}')

# Bot startup
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('alden', alden))  # Start the ALDEN questionnaire
    app.add_handler(CommandHandler('history', history))
    app.add_handler(CommandHandler('restart', restart))
    app.add_handler(CommandHandler('suggest', suggest))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))  # Handle user responses

    app.run_webhook(
        listen = "0.0.0.0",
        port = int(os.environ.get("PORT", 8443)),
        webhook_url = f"https://telemd.onrender.com/{TELEGRAM_TOKEN}"
    )