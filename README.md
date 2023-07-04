# nozomi

Nozomi is a Discord interaction layer built on top of
[hikari](https://github.com/hikari-py/hikari).

## Install

```sh
pip install nozomi
```

## Quick Tutorial

Using slash commands is very straightforward.
Nozomi does all the binding and registering required:

```python
import hikari
import nozomi

bot = hikari.GatewayBot("<your_discord_bot_token>")
controller = nozomi.controller(bot)

@controller.command()
async def hello(context: nozomi.Context):
    await context.message("Hello")
```

Using components just requires a simple binding operation:

```python
@controller.command(name="choice")
async def yes_no(context: nozomi.Context):
    await context.embed(
        title="Choice",
        description="Click one",
        components=[say_yes, say_no]
    )

@controller.button.success(label="Yes")
async def say_yes():
    await context.send("Yes")

@controller.button(label="No")
async def say_no():
    await context.send("No")
```

You can use the same decorators on classes if that's more convenient.
It can be useful if you want to keep some context.

```python
@controller.command
class Choice:
    async def __init__(self):
        self.user: Optional[hikari.User] = None

    async def __call__(self, context: nozomi.Context):
        self.user = context.user
        await context.embed(
            title="Choice",
            description="Click one",
            components=[self.say_yes, self.say_no]
        )

    @controller.button.success
    async def yes(self):
        if context.user != self.user:
            raise nozomi.Error(f"Only <@{self.user.id}> can choose yes.")
        await context.send("Yes")

    @controller.button
    async def no(self):
        await context.send("No")
```

You can declare subcommands very simply:

```python
base = controller.command_group(name="base")

# invoked by users with:
# /base hello
@controller.command(parent=base)
async def hello(context: nozomi.Context):
    await context.message("Hello")
```

You can use the same syntax to build complex command trees:

```python
base = controller.command_group(name="base")
foo = controller.command_group(name="foo", parent="base")
bar = controller.command_group(name="bar", parent="base")

# invoked by users with:
# /base foo hello
@controller.command(parent=foo)
async def hello(context: nozomi.Context):
    await context.message("Hello")

@controller.command(parent=foo)
async def world(context: nozomi.Context):
    await context.message("World")

@controller.command(parent=bar)
async def byebye(context: nozomi.Context):
    await context.message("Bye bye")

@controller.command(parent=bar)
async def world(context: nozomi.Context):
    await context.message("World")
```

And you can chain commands to provide smart and rich workflows.

```python
@controller.command
async def hello(context: nozomi.Context):
    await context.message("Hello")
    # by default, the chained command reuses the existing message
    await context.chain(world, follow_up=True)

@controller.command
async def world(context: nozomi.Context):
    await context.message("Hello")
```

You can also chain commands from components:

```python
@controller.command
async def hello(context: nozomi.Context):
    await context.embed(
        title="Hello",
        description="Click next to continue",
        components=nozomi.button.primary(nozomi.chain(world), label="Next")
    )

@controller.command
async def world(context: nozomi.Context):
    await context.embed(
        title="World",
        description="Click previous to go back",
        components=nozomi.button.primary(nozomi.chain(hello))
    )
```
