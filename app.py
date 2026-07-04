import os
import io
import logging
from flask import Flask, request, jsonify
import telegram
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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY")
WEBHOOK_URL = os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("PUBLIC_URL")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
if not STABILITY_API_KEY:
    raise ValueError("STABILITY_API_KEY environment variable is required")

# Conversation states
WAITING_FOR_PROMPT, WAITING_FOR_STYLE, WAITING_FOR_SIZE = range(3)

# Available styles
STYLES = {
    "photographic": "Photographic",
    "digital-art": "Digital Art", 
    "anime": "Anime",
    "cinematic": "Cinematic",
    "fantasy-art": "Fantasy Art",
    "pixel-art": "Pixel Art"
}

# Available sizes
SIZES = {
    "square": "512x512",
    "portrait": "512x768",
    "landscape": "768x512"
}

# Flask app for webhook
flask_app = Flask(__name__)

# Telegram Application instance
application = None

def get_keyboard(buttons_dict, columns=2):
    """Create an inline keyboard from a dictionary of options."""
    keyboard = []
    row = []
    for i, (key, label) in enumerate(buttons_dict.items()):
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
        "I can generate stunning images from your text descriptions using AI.\n\n"
        "**How to use:**\n"
        "1. Use /image to start generating an image\n"
        "2. Describe what you want to see\n"
        "3. Choose a style and size\n"
        "4. Wait for your AI-generated artwork!\n\n"
        "Try it now: /image"
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
        "• Use the available style presets\n"
        "• Try different sizes for different uses"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ongoing conversation."""
    await update.message.reply_text("🔄 Operation cancelled. Use /image to start again.")
    return ConversationHandler.END

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start image generation process."""
    await update.message.reply_text(
        "✏️ Please describe the image you want to create.\n\n"
        "Example: *A futuristic city with neon lights and flying cars at sunset*",
        parse_mode="Markdown"
    )
    return WAITING_FOR_PROMPT

async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user prompt input."""
    context.user_data['prompt'] = update.message.text
    
    # Show style selection
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
    
    # Show size selection
    size_keyboard = get_keyboard(SIZES)
    await query.edit_message_text(
        f"✅ Style selected: **{STYLES[query.data]}**\n\n"
        "📐 Now choose an image size:",
        parse_mode="Markdown",
        reply_markup=size_keyboard
    )
    return WAITING_FOR_SIZE

async def handle_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle size selection and generate image."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['size'] = query.data
    size_dimensions = SIZES[query.data]
    
    await query.edit_message_text(
        f"🎨 **Generating your image...**\n\n"
        f"Prompt: {context.user_data['prompt']}\n"
        f"Style: {STYLES[context.user_data['style']]}\n"
        f"Size: {size_dimensions}\n\n"
        "⏳ This may take 10-30 seconds..."
    )
    
    try:
        # Generate image using Stability AI API
        image_data = await generate_image(
            prompt=context.user_data['prompt'],
            style=context.user_data['style'],
            size=size_dimensions
        )
        
        # Send generated image
        await query.message.reply_photo(
            photo=image_data,
            caption=f"🖼️ **Generated Image**\n\nPrompt: {context.user_data['prompt']}"
        )
        
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        await query.message.reply_text(
            "❌ Sorry, I couldn't generate the image. Please try again with a different prompt."
        )
    
    return ConversationHandler.END

async def generate_image(prompt: str, style: str, size: str):
    """Generate image using Stability AI API."""
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "text_prompts": [
            {
                "text": prompt,
                "weight": 1.0
            }
        ],
        "cfg_scale": 7,
        "height": int(size.split('x')[1]),
        "width": int(size.split('x')[0]),
        "samples": 1,
        "steps": 30
    }
    
    # Add style preset if available
    if style == "photographic":
        data["style_preset"] = "photographic"
    elif style == "digital-art":
        data["style_preset"] = "digital-art"
    elif style == "anime":
        data["style_preset"] = "anime"
    elif style == "cinematic":
        data["style_preset"] = "cinematic"
    elif style == "fantasy-art":
        data["style_preset"] = "fantasy-art"
    elif style == "pixel-art":
        data["style_preset"] = "pixel-art"
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code != 200:
        raise Exception(f"API error: {response.text}")
    
    # Parse the response and return image data
    result = response.json()
    image_data = result.get("artifacts", [])[0].get("base64")
    
    if not image_data:
        raise Exception("No image generated")
    
    # Decode base64 to bytes
    image_bytes = base64.b64decode(image_data)
    
    # Convert to BytesIO for Telegram
    img = Image.open(io.BytesIO(image_bytes))
    img_io = io.BytesIO()
    img.save(img_io, format='PNG')
    img_io.seek(0)
    
    return img_io

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

# Flask webhook routes
@flask_app.route('/webhook', methods=['POST'])
async def webhook():
    """Handle incoming Telegram webhook requests."""
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@flask_app.route('/')
def index():
    """Health check endpoint."""
    return jsonify({
        "status": "running",
        "bot": "ArtSparkoBot",
        "version": "1.0.0"
    })

@flask_app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

def setup_application():
    """Configure and return the Telegram application."""
    global application
    
    # Create application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    
    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("image", image_command)],
        states={
            WAITING_FOR_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prompt)
            ],
            WAITING_FOR_STYLE: [
                CallbackQueryHandler(handle_style, pattern="|".join(STYLES.keys()))
            ],
            WAITING_FOR_SIZE: [
                CallbackQueryHandler(handle_size, pattern="|".join(SIZES.keys()))
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    
    return application

if __name__ == "__main__":
    # Set up the application
    app = setup_application()
    
    # Set webhook if URL is available
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        logger.warning("No webhook URL provided. Running in polling mode.")
        app.run_polling()
    
    # Run Flask app
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host='0.0.0.0', port=port, debug=False)
