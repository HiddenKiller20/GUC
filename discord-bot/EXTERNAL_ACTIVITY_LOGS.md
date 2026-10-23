# External activity logs

Destination: `1554625091520823366` in the configured GUC guild.

Records new visible external bot, app, and webhook messages. Includes author ID, application ID when supplied, source message link, time, and interaction user when Discord supplies one. Unknown users stay unknown; nearby messages are never used to guess attribution. Message content is not copied. No bans or other moderation actions are performed by this module.

The bot requires View Channel on monitored channels and View Channel, Send Messages, Embed Links on the destination. Ephemeral replies, private interactions and channels the bot cannot see cannot be logged. This is not an inventory of every installed app or a complete command audit. No historical backfill is performed.

New records are queued in SQLite and delivered every 10 seconds, up to 10 per batch. Failed sends remain queued across restarts when the database is persistent. Repeated gateway delivery of a message is deduplicated by message ID. A process crash after sending but before recording success can result in a duplicate log. Source activity in the log channel itself and this bot's messages are excluded to prevent loops. Mentions do not ping users.

Tests: `python -m unittest test_external_activity_logs.py` from discord-bot.
