from kutana import Plugin

plugin = Plugin(name="Echo")

@plugin.on_commands(["echo"])
async def _(msg, ctx):
    await ctx.reply(ctx.body, attachments=msg.attachments)