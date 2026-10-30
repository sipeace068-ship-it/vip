import asyncio
import logging
import os

from deep_translator import GoogleTranslator
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# This dictionary stores each user's selected language while the bot runs.
USER_LANGUAGES = {}


def get_language_name(language):
    """Validate a language name or code."""
    language = language.strip().lower()
    supported = GoogleTranslator().get_supported_languages(as_dict=True)

    if language in supported:
        return language

    for name, code in supported.items():
        if code.lower() == language:
            return name

    raise ValueError("Unsupported language")


async def translate_text(text, target):
    """Run translation without blocking Telegram's event loop."""
    language = get_language_name(target)

    return await asyncio.to_thread(
        GoogleTranslator(
            source="auto",
            target=language,
        ).translate,
        text,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🌍 Welcome to Universal Translator!\n\n"
        "I can translate text into many languages.\n\n"
        "Commands:\n"
        "/setlang Spanish - Set your language\n"
        "/translate French Hello world - Translate text\n"
        "/mylang - View your selected language\n"
        "/languages - Show available languages\n"
        "/stop - Disable automatic translation\n\n"
        "First, choose your language using /setlang."
    )


async def set_language(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /setlang Spanish\n"
            "You can also use a language code, such as /setlang es."
        )
        return

    target = " ".join(context.args)

    try:
        language = get_language_name(target)

        USER_LANGUAGES[update.effective_user.id] = language

        await update.effective_message.reply_text(
            f"✅ Your language is now {language.title()}.\n\n"
            "Send me a message and I'll translate it automatically."
        )

    except ValueError:
        await update.effective_message.reply_text(
            "❌ Language not recognized.\n"
            "Try /languages to see available languages."
        )
    except Exception:
        logger.exception("Could not set language")
        await update.effective_message.reply_text(
            "⚠️ The language service is temporarily unavailable. "
            "Please try again."
        )


async def translate_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage: /translate Spanish Hello, how are you?"
        )
        return

    target = context.args[0]
    text = " ".join(context.args[1:])

    try:
        translated = await translate_text(text, target)

        if not translated:
            raise ValueError("Empty translation")

        await update.effective_message.reply_text(
            f"🌍 Translation ({target.title()}):\n\n{translated}"
        )

    except ValueError:
        await update.effective_message.reply_text(
            "❌ Language not recognized. Use /languages to see options."
        )
    except Exception:
        logger.exception("Translation command failed")
        await update.effective_message.reply_text(
            "⚠️ Translation failed. Please try again later."
        )


async def languages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        supported = GoogleTranslator().get_supported_languages()
        names = ", ".join(name.title() for name in supported)

        await update.effective_message.reply_text(
            "🌍 Supported languages:\n\n" + names
        )

    except Exception:
        logger.exception("Could not retrieve languages")
        await update.effective_message.reply_text(
            "⚠️ Could not load languages. Please try again later."
        )


async def my_language(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    language = USER_LANGUAGES.get(update.effective_user.id)

    if language:
        await update.effective_message.reply_text(
            f"🌍 Your selected language is {language.title()}."
        )
    else:
        await update.effective_message.reply_text(
            "You haven't selected a language.\n"
            "Use /setlang Spanish, for example."
        )


async def stop_translation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    USER_LANGUAGES.pop(update.effective_user.id, None)

    await update.effective_message.reply_text(
        "✅ Automatic translation is disabled.\n"
        "Use /setlang followed by a language to enable it again."
    )


async def translate_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not user or not message or not message.text:
        return

    target = USER_LANGUAGES.get(user.id)

    if not target:
        await message.reply_text(
            "🌍 Choose your language first:\n"
            "/setlang Spanish\n\n"
            "Or translate one message directly:\n"
            "/translate French Hello there"
        )
        return

    try:
        translated = await translate_text(message.text, target)

        if not translated:
            raise ValueError("Empty translation")

        await message.reply_text(translated)

    except Exception:
        logger.exception("Automatic translation failed")
        await message.reply_text(
            "⚠️ Translation failed. Please try again later."
        )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Unhandled Telegram error",
        exc_info=context.error,
    )


def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add your token in Railway Variables."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setlang", set_language))
    app.add_handler(CommandHandler("translate", translate_command))
    app.add_handler(CommandHandler("languages", languages))
    app.add_handler(CommandHandler("mylang", my_language))
    app.add_handler(CommandHandler("stop", stop_translation))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            translate_message,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("Translation bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
