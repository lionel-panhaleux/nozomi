import hikari
import logging
from types import FunctionType, MethodType
from typing import Union, Optional

import stringcase
from . import registry


Decorated = Union[FunctionType, MethodType, type]
Bot = Union[hikari.GatewayBot, hikari.RESTBot]
Interaction = Union[
    hikari.CommandInteraction,
    hikari.ComponentInteraction,
    hikari.AutocompleteInteraction,
    hikari.ModalInteraction,
]


logger = logging.getLogger("nozomi")


class NozomiError(RuntimeError):
    pass


def split_text(s, limit):
    """Utility function to split a text at a convenient spot."""
    if len(s) < limit:
        return s, ""
    index = s.rfind("\n", 0, limit)
    rindex = index + 1
    if index < 0:
        index = s.rfind(" ", 0, limit)
        rindex = index + 1
        if index < 0:
            index = limit
            rindex = index
    return s[:index], s[rindex:]


def paginate_embed(embed: hikari.Embed) -> list[hikari.Embed]:
    """Utility function to paginate a Discord Embed"""
    embeds = []
    fields = []
    base_title = embed.title
    description = ""
    page = 1
    logger.debug("embed: %s", embed)
    while embed:
        if embed.description:
            embed.description, description = split_text(embed.description, 2048)
        while embed.fields and (len(embed.fields) > 15 or description):
            fields.append(embed.fields[-1])
            embed.remove_field(-1)
        embeds.append(embed)
        if description or fields:
            page += 1
            embed = hikari.Embed(
                title=base_title + f" ({page})",
                description=description,
            )
            for f in fields:
                embed.add_field(name=f.name, value=f.value, inline=f.is_inline)
            description = ""
            fields = []
        else:
            embed = None
    if len(embeds) > 10:
        raise ValueError("Embed too large to paginate")
    return embeds


class Command:
    def __init__(self, decorated: Decorated, name: Optional[str] = None, description: Optional[str] = None):
        self.decorated: Decorated = decorated
        self.name = name or stringcase.spinalcase(decorated.name)
        self.description = description or stringcase.spinalcase(decorated.name)
        registry.COMMANDS[self.name] = self

    
    def __call__(self, decorated: Decorated):
        

class FunctionCommand(Command):
    async def __call__(self, *args, **kwargs):
        return await self.decorated(*args, **kwargs)


class MethodCommand(Command):
    async def __call__(self, instance, *args, **kwargs):
        return await self.decorated(instance, *args, **kwargs)


class ClassCommand(Command):
    async def __call__(self, *args, **kwargs):
        return await self.decorated()(*args, **kwargs)


class Controller:
    def __init__(self, bot: Bot):
        self.bot: Bot = bot

    class CommandDecorator:
        def __init__(self, *, name: Optional[str] = None, parent: Command = None):
            self.name = name or None
            self.parent = parent

        def __call__(self, decorated: Decorated):
            if isinstance(decorated, MethodType):
                return MethodCommand(decorated)
            elif isinstance(decorated, FunctionType):
                return FunctionCommand(decorated)
            elif isinstance(decorated, type):
                return ClassCommand(decorated)
            raise TypeError("command can only decorate functions, methods or classes")

    def command(self, decorated: Optional[Decorated] = None, **kwargs):
        if decorated is not None:
            return self.CommandDecorator()(decorated)
        return self.CommandDecorator(**kwargs)

    class Context:
        def __init__(
            self, interaction: Interaction, rest: Optional[hikari.api.RESTClient] = None
        ):
            self.interaction: Interaction = interaction
            self.rest: hikari.api.RESTClient = rest
            self.message: Optional[hikari.Message] = None
            self.ephemeral: Optional[bool] = None

        async def chain(self, command: Command, *, follow_up: bool = False):
            if follow_up and not isinstance(self.bot, hikari.GatewayBot):
                raise ValueError("follow_up can only be used with a GatewayBot")
            return await command(self)

        async def defer(self, ephemeral: bool = False, follow_up=False):
            if self.message:
                return
            self.ephemeral = ephemeral
            flags = hikari.MessageFlag.EPHEMERAL if ephemeral else hikari.UNDEFINED
            if (
                isinstance(self.interaction, hikari.ComponentInteraction)
                and not follow_up
            ):
                type = hikari.ResponseType.DEFERRED_MESSAGE_UPDATE
            else:
                type = hikari.ResponseType.DEFERRED_MESSAGE_CREATE
            self.rest.create_interaction_response(
                self.interaction,
                self.interaction.token,
                type,
                flags=flags,
            )

        async def send(
            self, *args, ephemeral: bool = False, follow_up: bool = False, **kwargs
        ):
            if "embed" in kwargs:
                kwargs.setdefault("embeds", paginate_embed(kwargs.pop("embed")))
            flags = hikari.UNDEFINED
            if self.ephemeral is None or (follow_up and self.message):
                self.ephemeral = ephemeral
                if ephemeral:
                    flags = hikari.MessageFlag.EPHEMERAL
            kwargs.setdefault("flags", flags)
            if not self.message:
                if (
                    isinstance(self.interaction, hikari.ComponentInteraction)
                    and not follow_up
                ):
                    type = (hikari.ResponseType.MESSAGE_UPDATE,)
                else:
                    type = hikari.ResponseType.MESSAGE_CREATE
                self.rest.create_interaction_response(
                    self.interaction.id,
                    self.interaction.token,
                    type,
                    **kwargs,
                )
            elif follow_up:
                self.rest.execute_webhook(
                    self.interaction.application_id,
                    self.interaction.token,
                    *args,
                    **kwargs,
                )
            else:
                self.rest.edit_interaction_response(
                    self.interaction.application_id,
                    self.interaction.token,
                    *args**kwargs,
                )

    def context(self, interaction: Interaction):
        raise NotImplementedError()

    async def dispatch_interaction(self, event: hikari.InteractionCreateEvent):
        if event.interaction.type == hikari.InteractionType.APPLICATION_COMMAND:
            return await self.dispatch_command(event.interaction)
        elif event.interaction.type == hikari.InteractionType.MESSAGE_COMPONENT:
            return await self.dispatch_component(event.interaction)
        elif event.interaction.type == hikari.InteractionType.AUTOCOMPLETE:
            return await self.dispatch_autocomplete(event.interaction)
        elif event.interaction.type == hikari.InteractionType.MODAL_SUBMIT:
            return await self.dispatch_modal(event.interaction)

    async def dispatch_command(self, interaction: hikari.CommandInteraction):
        options = getattr(interaction, "options", None)
        action = registry.COMMAND_ID_TO_INTERACTION[interaction.id]
        # go down the command groups tree
        # for now, Discord only allows a maximum of three levels depth
        # command > sub_command_group > sub_command
        while options and options[0].type in (
            hikari.OptionType.SUB_COMMAND,
            hikari.OptionType.SUB_COMMAND_GROUP,
        ):
            try:
                action = action[options[0].name]
            except (KeyError, TypeError):
                raise ValueError(f"unexpected subcommand {interaction}")
            options = getattr(options[0], "options", None)
        context = self.context()
        options = {
            stringcase.snakecase(option.name): option.value for option in options
        }
        return await self.execute(action, context, **options)

    async def dispatch_component(self, interaction: hikari.ComponentInteraction):
        action = registry.COMPONENT_ID_TO_INTERACTION[interaction.custom_id]
        context = self.context()
        return await self.execute(action, context)

    async def dispatch_autocomplete(self, interaction: hikari.AutocompleteInteraction):
        action = registry.AUTOCOMPLETE_ID_TO_INTERACTION[interaction.command_id]
        context = self.context()
        return await self.execute(action, context)

    async def dispatch_modal(self, interaction: hikari.ModalInteraction):
        action = registry.MODAL_ID_TO_INTERACTION[interaction.custom_id]
        context = self.context()
        return await self.execute(action, context)

    async def execute(self, action, context, **options):
        response = None
        try:
            response = await action(context, **options)
        except NozomiError as err:
            if err.args:
                response = err.args[0]
            else:
                response = "Failed"
        except Exception:
            logger.exception("Interaction exception")
            response = "Internal server error"
        if response:
            if isinstance(response, hikari.Embed):
                response = paginate_embed(response)
            context.send(response)


class GatewayController:
    def __init__(self, bot: hikari.GatewayBot):
        super().__init__(bot)
        self.bot.listen(hikari.StartedEvent)(self.register_application_commands)
        self.bot.listen(hikari.InteractionCreateEvent)(self.dispatch_interaction)

    def context(self, interaction: Interaction):
        return self.Context(interaction, rest=self.bot.rest)

    def defer(self):
        self.bot.rest


class RESTController:
    def __init__(self, bot: hikari.RESTBot):
        self.bot: hikari.RESTBot = bot
        self.bot.add_startup_callback(self.register_application_commands)
        self.bot.set_listener(
            hikari.InteractionType.APPLICATION_COMMAND, self.dispatch_command
        )
        self.bot.set_listener(
            hikari.InteractionType.MESSAGE_COMPONENT, self.dispatch_component
        )
        self.bot.set_listener(
            hikari.InteractionType.AUTOCOMPLETE, self.dispatch_autocomplete
        )
        self.bot.set_listener(hikari.InteractionType.MODAL_SUBMIT, self.dispatch_modal)

    def context(self, interaction: Interaction):
        return self.Context(interaction)


def controller(bot: Union[hikari.GatewayBot, hikari.RESTBot]) -> Controller:
    if isinstance(bot, hikari.GatewayBot):
        return GatewayController(bot)
    elif isinstance(bot, hikari.RESTBot):
        return RESTController(bot)
    raise TypeError("bot must be a GatewayBot or RESTBot instance")
