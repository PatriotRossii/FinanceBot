from kutana import Plugin

from plugins.monitor.monitor import Monitor, ListingType

plugin = Plugin(name="Echo")
monitor = Monitor.get_instance()


# /add {symbol} {type}
# {type}: Stock|Currency
@plugin.on_commands(["add"])
async def _(msg, ctx):
    args = ctx.body.split()
    if len(args) != 1:
        return await ctx.reply("Неверный формат ввода")

    info = monitor.parse(msg.sender_id, args[0])
    if not info:
        return await ctx.reply("Неверный формат ввода")
    monitor.add_subscriber(info)

    return await ctx.reply("Успешная операция", attachments=msg.attachments)
