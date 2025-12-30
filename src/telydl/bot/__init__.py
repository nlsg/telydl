import logging
import typing
import time
from functools import partial
from datetime import datetime

import re

from telegram import Update, ForceReply, User, Message, ReactionTypeEmoji
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

if typing.TYPE_CHECKING:
    from telegram.ext import Application
    from telydl.downloaders.abstract import (
        DownloaderProtocol,
        DownloadStatus,
        DownloadCallback,
    )

_logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r"https?://[^\s<>\"]+",
    re.IGNORECASE,
)


class TelyDlBot:
    def __init__(
        self, token: str, downloader: "DownloaderProtocol", whitelist: list[int]
    ):
        self.app: Application = ApplicationBuilder().token(token).build()
        self.downloader = downloader
        self._started = False
        self.whitelist = whitelist

        self.app.add_handler(CommandHandler("start", self._start_command))
        self.app.add_handler(CommandHandler("help", self._help_command))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._process_text_command)
        )

    async def start(self):
        if self._started:
            return

        _logger.info("Starting Telegram bot")

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        self._started = True

    async def stop(self):
        if not self._started:
            return

        _logger.info("Stopping Telegram bot")

        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

        self._started = False

    def _check_user(self, user: User):
        return user.id in self.whitelist

    @staticmethod
    def get_urls(message: Message) -> list[str] | str | None:
        try:
            if url := message.link_preview_options.url:
                return url
        except AttributeError:
            ...
        return re.findall(URL_REGEX, message.text) or None

    async def _start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = update.effective_user
        await update.message.reply_html(
            rf"Hi {user.mention_html()}!",
            reply_markup=ForceReply(selective=True),
        )

    async def _help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text("Help!")

    async def _process_text_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        message = update.message
        chat_id = update.effective_chat.id

        if not self._check_user(update.effective_user):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"{update.effective_user.name} is not authorized, authorization request sent!",
            )
            # await self._send_auth_request(update.effective_user) #TODO
            return

        await message.reply_text(disable_web_page_preview=True, text="auth successful")

        if not (urls := self.get_urls(message)):
            await context.bot.send_message(chat_id=chat_id, text="invalid URL!")
            return

        start_time = time.perf_counter()
        results = await self.downloader.download(
            urls, status_callback=self._get_callback(update=update, context=context)
        )
        if all(results):
            await message.set_reaction(ReactionTypeEmoji("❤️"))
        else:
            await message.set_reaction(ReactionTypeEmoji("👎"))
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"processing urls finished:\nurls:{urls}\ntime: {time.perf_counter() - start_time}\nfinished:{datetime.now()}",
            disable_web_page_preview=True,
        )

    def _get_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> "DownloadCallback":
        chat_id = update.effective_chat.id

        def callback(status: "DownloadStatus", message: str):
            if status == "info":
                return context.bot.send_message(
                    chat_id=chat_id, text=message, disable_notification=True
                )
            elif status == "success":
                return context.bot.send_message(chat_id=chat_id, text=message)
            elif status == "error":
                return context.bot.send_message(chat_id=chat_id, text=message)

        return callback
