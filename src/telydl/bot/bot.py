from typing import Iterable
import logging
import typing
import os
import time
import functools
from datetime import datetime
from pathlib import Path

import re

from telegram import Update, ForceReply, Message, ReactionTypeEmoji, BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from telydl.util import run_shell, URL_REGEX

if typing.TYPE_CHECKING:
    from telegram.ext import Application
    from telydl.downloaders.abstract import (
        DownloaderProtocol,
        DownloadStatus,
    )

_logger = logging.getLogger(__name__)

type CommandPredicate = callable[[Update, ContextTypes.DEFAULT_TYPE], bool]


class TelyDlBot:
    def __init__(
        self, token: str, downloader: "DownloaderProtocol", whitelist: list[int]
    ):
        self.app: Application = ApplicationBuilder().token(token).build()
        self.downloader = downloader
        self._started = False
        self.whitelist = whitelist

    async def start(self):
        if self._started:
            return

        _logger.info("Starting Telegram bot")

        self.app.add_handlers(
            [
                CommandHandler("help", self._help_command),
                CommandHandler(
                    "list",
                    self.require(
                        [self.is_authorized], reason="authentication required"
                    )(self._list_command),
                ),
                CommandHandler(
                    "get_log",
                    self.require(
                        [self.is_authorized], reason="authentication required"
                    )(self._get_log_command),
                ),
                CommandHandler(
                    "rsync",
                    self.require(
                        [self.is_authorized], reason="authentication required"
                    )(self._rsync_command),
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, self._process_text_command
                ),
            ]
        )
        self.app.add_error_handler(self._error_handler)

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        await self.app.bot.set_my_commands(
            [
                # BotCommand("help", "list download archive"),
                BotCommand("list", "list download archive"),
                BotCommand("get_log", "get application logs"),
                BotCommand("rsync", "run sync command."),
            ]
        )

        self._started = True

    async def stop(self):
        if not self._started:
            return

        _logger.info("Stopping Telegram bot")

        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

        self._started = False

    @staticmethod
    def require(
        predicates: Iterable[CommandPredicate] | CommandPredicate,
        reason: str | None = None,
    ):
        """
        Abort a Telegram command if predicate(update, context) returns True.
        Optionally reply with a reason.
        """

        predicates = (
            predicates
            if isinstance(predicates, Iterable)
            else [
                predicates,
            ]
        )

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if all(predicate(update, context) for predicate in predicates):
                    return await func(update, context)
                if reason and update.message:
                    await update.message.reply_text(reason)
                return

            return wrapper

        return decorator

    @staticmethod
    def get_urls(message: Message) -> list[str] | str | None:
        try:
            if url := message.link_preview_options.url:
                return url
        except AttributeError:
            ...
        return re.findall(URL_REGEX, message.text) or None

    def is_authorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        return update.effective_user.id in self.whitelist or _logger.warning(
            f"unauthorized user: {update.effective_user}"
        )

    # handlers

    async def _start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = update.effective_user
        await update.message.reply_html(
            rf"Hi {user.mention_html()}!",
            reply_markup=ForceReply(selective=True),
        )

    async def _rsync_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        output = run_shell(*os.getenv("TELYDL_RSYNC").split(" "))
        await update.message.reply_markdown(output)

    async def _list_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        base_dir = str(self.downloader.base_directory.resolve())
        output = (
            "TREE:\n"
            + run_shell(
                "tree",
                base_dir,
            )
            + "\n\nDU: "
            + run_shell("du", "-h", base_dir)
        )
        await update.message.reply_markdown(output)

    async def _get_log_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_document(Path("bot.log").resolve())

    async def _help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text("Help!")

    async def _error_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        msg = f"bot error: {context.error}"
        _logger.error(msg)
        update.char_
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    async def _process_text_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        message = update.message
        chat_id = update.effective_chat.id

        if not self.is_authorized(update=update, context=context):
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

        async def status_callback(status: "DownloadStatus", message: str):
            message = f"[{status}]: {message}"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                disable_notification=status != "error",
                disable_web_page_preview=not any("spotify" in u for u in urls),
            )

        start_time = time.perf_counter()
        results = await self.downloader.download(urls, status_callback=status_callback)
        if all(results):
            await message.set_reaction(ReactionTypeEmoji("❤️"))
        else:
            await message.set_reaction(ReactionTypeEmoji("👎"))
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"processing urls finished:\n{results=}\ntime: {time.perf_counter() - start_time}\nfinished:{datetime.now()}",
            disable_web_page_preview=True,
        )
