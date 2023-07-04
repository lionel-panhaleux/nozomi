import asyncio
import inspect
from typing import Any, Union, Optional

import hikari
import hikari.api.special_endpoints


Bot = Union[hikari.GatewayBot, hikari.RESTBot]
Interaction = Union[
    hikari.CommandInteraction,
    hikari.ComponentInteraction,
    hikari.AutocompleteInteraction,
    hikari.ModalInteraction,
]


class Executor:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.ephemeral: Optional[bool] = None
        self.message: Optional[hikari.Message] = None

    class Context:
        def __init__(self, executor, interaction):
            self._executor = executor
            self.interaction = interaction

        async def defer(self, ephemeral: bool = False):
            self.bot.re
            self._executor.ephemeral = ephemeral
            self._executor.defer.set()

        async def send(
            self,
            *args,
            follow_up: bool = False,
            ephemeral: Optional[bool] = None,
            **kwargs
        ):
            if ephemeral is not None:
                if (
                    follow_up and self._executor.message
                ) or self._executor.ephemeral is None:
                    self._executor.ephemeral = ephemeral
                else:
                    raise ValueError("ephemeral has already been set, cannot reset")
            if not self.message:
                self._executor.bot.
    
    async def _run(self, interaction: Interaction, action: Any, **kwargs):
        if inspect.isclass(action):
            action = action().__call__
        if not inspect.iscoroutinefunction(action):
            raise TypeError(
                "action should be a coroutine or a class with a coroutine __call__"
            )
        await action(self, **kwargs)
        return


class AsyncExecutor:
    pass
