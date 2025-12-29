from typing import Callable, Awaitable
import asyncio
import logging
import typing
import time
from datetime import datetime

import re
from urllib.parse import urlparse, urlunparse

from telegram import Update, ForceReply, User, Message, ReactionTypeEmoji
from telegram.constants import ReactionEmoji
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
    from telydl.downloaders.abstract import DownloaderProtocol

_logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r"https?://[^\s<>\"]+",
    re.IGNORECASE,
)


class TelyDlBot:
    def __init__(self, token: str, downloader: "DownloaderProtocol"):
        self.app: Application = ApplicationBuilder().token(token).build()
        self.downloader = downloader
        self._started = False

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
        return user.first_name == "nils"

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
            await message.reply_text(
                f"{update.effective_user.name} is not authorized, authorization request sent!"
            )
            # await self._send_auth_request(update.effective_user)
            return

        if not (urls := self.get_urls(message)):
            await context.bot.send_message(chat_id=chat_id, text="invalid URL!")
            return

        start_time = time.perf_counter()

        if await self.downloader.download(
            urls,
            start_callback=lambda url: context.bot.send_message(
                chat_id=chat_id, text=f"started: {url}"
            ),
        ):
            await message.set_reaction(ReactionTypeEmoji("❤️"))
        else:
            await message.set_reaction(ReactionTypeEmoji("👎"))
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"processing url took:\nurls:{urls}\ntime: {time.perf_counter() - start_time}\nfinished:{datetime.now()}",
        )


"""
https://open.spotify.com/intl-de/track/6bIme7LRiGdVuYFSVmMgbd?si=3dd8ad519f5843b0

https://www.youtube.com/watch?v=KUetdiD0Bo4&pp=ygUcbGFuZGhvdXNlICYgcmFkZGFudHplIHJvYm90cw%3D%3D

https://www.youtube.com/watch?v=qkAbiXiAgF8&pp=ygUcbGFuZGhvdXNlICYgcmFkZGFudHplIHJvYm90cw%3D%3D
https://www.youtube.com/watch?v=Kih04PB6RZA&pp=ygUcbGFuZGhvdXNlICYgcmFkZGFudHplIHJvYm90cw%3D%3D
"""
