from abc import ABC, abstractmethod

from ..bot_component import BotComponent


class BotState(BotComponent, ABC):

    def __init__(self, bot):
        super().__init__(bot)
        # Share the single detected ScreenConfig (don't re-detect per state).
        self.window = bot.config.bot.screen

    @abstractmethod
    def handle(self, screen):
        pass
