# ArtSparkoBot - AI Image Generation Telegram Bot

**@ArtSparkoBot** is a Telegram bot that generates images from text descriptions using Stability AI's image generation models.

## Features

- 🎨 Text-to-image generation
- 🖌️ Multiple art styles (photographic, digital art, anime, cinematic, fantasy-art, pixel-art)
- 📐 Multiple image sizes (square, portrait, landscape)
- 💬 Interactive conversation flow
- ⚡ Fast response with clear feedback

## Quick Deploy to Railway

1. **Fork this repository** to your GitHub account

2. **Get API Keys**:
   - Telegram Bot Token from @BotFather
   - Stability AI API Key from [Stability AI Platform](https://platform.stability.ai/)

3. **Deploy on Railway**:
   - Go to [Railway](https://railway.com/)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your forked repository
   - Add environment variables in Railway dashboard:
     - `TELEGRAM_BOT_TOKEN`: Your bot token
     - `STABILITY_API_KEY`: Your Stability AI key

4. **Done!** Your bot will be running 24/7.

## Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/artsparkobot.git
cd artsparkobot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env
# Edit .env with your API keys

# Run the bot
python app.py
