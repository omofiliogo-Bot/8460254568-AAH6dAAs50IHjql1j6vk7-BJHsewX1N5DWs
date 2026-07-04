import os
import io
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
import requests
from PIL import Image
import base64
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY")

if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN is required")
    exit(1)
if not STABILITY_API_KEY:
    logger.error("STABILITY_API_KEY is required")
    exit(1)

# Conversation states
WAITING_FOR_PROMPT, WAITING_FOR_STYLE, WAITING_FOR_SIZE = range(3)

# Available styles
STYLES = {
    "photographic": "📷 Photographic",
    "digital-art": "🎨 Digital Art",
    "anime": "🌸 Anime",
    "cinematic": "🎬 Cinematic",
    "fantasy-art": "🐉 Fantasy Art",
    "pixel-art": "🟦 Pixel Art"
}

# Available sizes
SIZES = {
    "512x512": "⬜ Square",
    "512x768": "📱 Portrait",
    "768x512": "🖥️ Landscape"
}

# Flask app
flask_app = Flask(__name__)
application = None

def get_keyboard(buttons_dict, columns=2):
    """Create an inline keyboard."""
    keyboard = []
    row = []
    for key, label in buttons_dict.items():
        row.append(InlineKeyboardButton(label, callback_data=key))
        if len(row) == columns:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    welcome_text = (
        f"🎨 Welcome {user.first_name} to **ArtSparkoBot**!\n\n"
        "I generate images from text using AI.\n\n"
        "**Commands:**\n"
        "/image - Start image generation\n"
        "/help - Show help\n"
        "/cancel - Cancel current operation"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "**ArtSparkoBot Commands:**\n\n"
        "/start - Welcome message\n"
        "/help - Show this help\n"
        "/image - Start image generation\n"
        "/cancel - Cancel current operation\n\n"
        "**Tips for better results:**\n"
        "• Be specific and descriptive\n"
        "• Mention style, mood, lighting\n"
        "• Try different styles and sizes"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ongoing conversation."""
    await update.message.reply_text("🔄 Cancelled. Use /image to start again.")
    return ConversationHandler.END

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start image generation process."""
    await update.message.reply_text(
        "✏️ Describe the image you want to create.\n\n"
        "Example: *A futuristic city with neon lights*",
        parse_mode="Markdown"
    )
    return WAITING_FOR_PROMPT

async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user prompt input."""
    context.user_data['prompt'] = update.message.text
    style_keyboard = get_keyboard(STYLES)
    await update.message.reply_text(
        "🎨 Choose an art style:",
        reply_markup=style_keyboard
    )
    return WAITING_FOR_STYLE

async def handle_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle style selection."""
    query = update.callback_query
    await query.answer()
    context.user_data['style'] = query.data
    size_keyboard = get_keyboard(SIZES)
    await query.edit_message_text(
        f"✅ Style selected: **{STYLES[query.data]}**\n\n"
        "📐 Now choose size:",
        parse_mode="Markdown",
        reply_markup=size_keyboard
    )
    return WAITING_FOR_SIZE

async def handle_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle size selection and generate image."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['size'] = query.data
    size = query.data
    
    await query.edit_message_text(
        f"🎨 **Generating...**\n\n"
        f"Prompt: {context.user_data['prompt']}\n"
        f"Style: {STYLES[context.user_data['style']]}\n"
        f"Size: {size}\n\n"
        "⏳ Please wait 15-30 seconds..."
    )
    
    try:
        # Generate image
        image_data = await generate_image(
            prompt=context.user_data['prompt'],
            style=context.user_data['style'],
            size=size
        )
        
        # Send image
        await query.message.reply_photo(
            photo=image_data,
            caption=f"🖼️ **Generated Image**\n\nPrompt: {context.user_data['prompt']}"
        )
        
        # Delete generating message
        await query.message.delete()
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        await query.message.reply_text(
            f"❌ Couldn't generate image.\n\nError: {str(e)}"
        )
    
    return ConversationHandler.END

async def generate_image(prompt: str, style: str, size: str):
    """Generate image using Stability AI."""
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    width, height = map(int, size.split('x'))
    
    data = {
        "text_prompts": [{"text": prompt, "weight": 1.0}],
        "cfg_scale": 7,
        "height": height,
        "width": width,
        "samples": 1,
        "steps": 30
    }
    
    # Add style if valid
    style_presets = ["photographic", "digital-art", "anime", "cinematic", "fantasy-art", "pixel-art"]
    if style in style_presets:
        data["style_preset"] = style
    
    response = requests.post(url, headers=headers, json=data, timeout=60)
    
    if response.status_code != 200:
        error_msg = response.json().get('message', response.text)
        raise Exception(f"API Error: {error_msg}")
    
    result = response.json()
    artifacts = result.get("artifacts", [])
    
    if not artifacts:
        raise Exception("No image generated")
    
    image_base64 = artifacts[0].get("base64")
    if not image_base64:
        raise Exception("No image data")
    
    # Decode and return image
    image_bytes = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(image_bytes))
    img_io = io.BytesIO()
    img.save(img_io, format='PNG')
    img_io.seek(0)
    
    return img_io

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Error: {context.error}")

# Flask routes
@flask_app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook requests."""
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        # Process update
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.process_update(update))
        loop.close()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@flask_app.route('/')
def index():
    return jsonify({"status": "running", "bot": "ArtSparkoBot"})

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy"})

def setup_application():
    """Configure application."""
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("image", image_command)],
        states={
            WAITING_FOR_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prompt)
            ],
            WAITING_FOR_STYLE: [
                CallbackQueryHandler(handle_style)
            ],
            WAITING_FOR_SIZE: [
                CallbackQueryHandler(handle_size)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    
    return application

# Initialize
application = setup_application()
logger.info("ArtSparkoBot initialized")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host='0.0.0.0', port=port)
