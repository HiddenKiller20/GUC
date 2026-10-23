import sqlite3
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import discord
import external_activity_logs as logs

class Bot:
    user=NS(id=99)
    on_message=AsyncMock()
    on_ready=AsyncMock()
    def event(self, fn):
        setattr(self,fn.__name__,fn)
        return fn

class Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.b=NS(db=sqlite3.connect(':memory:'),GUILD_ID=1,bot=Bot())
        logs.install(self.b)
    def msg(self, **changes):
        data=dict(id=10,guild=NS(id=1),channel=NS(id=2),author=NS(id=3,bot=True),application_id=4,webhook_id=None,interaction_metadata=NS(id=8,user=NS(id=7)),created_at=datetime.now(timezone.utc))
        data.update(changes)
        return NS(**data)
    def count(self):
        return self.b.db.execute('SELECT count(*) FROM external_activity_log').fetchone()[0]
    async def test_capture_deduplicates_and_preserves_handler(self):
        msg=self.msg()
        await self.b.bot.on_message(msg)
        logs.capture(self.b,msg)
        self.assertEqual(self.count(),1)
        self.assertEqual(self.b.db.execute('SELECT user_id FROM external_activity_log').fetchone()[0],7)
        self.b.bot.on_message # original handler was awaited
        Bot.on_message.assert_awaited()
    async def test_filters(self):
        for msg in [self.msg(guild=None),self.msg(guild=NS(id=2)),self.msg(author=NS(id=99,bot=True)),self.msg(channel=NS(id=logs.LOG_CHANNEL_ID)),self.msg(author=NS(id=5,bot=False),application_id=None)]:
            logs.capture(self.b,msg)
        self.assertEqual(self.count(),0)
    async def test_unknown_and_webhook(self):
        logs.capture(self.b,self.msg(interaction_metadata=None,webhook_id=123,application_id=None))
        self.assertEqual(self.b.db.execute('SELECT user_id,kind FROM external_activity_log').fetchone(),(None,'Webhook message'))
    async def test_retry_no_mentions(self):
        logs.capture(self.b,self.msg())
        channel=NS(permissions_for=lambda _:NS(view_channel=True,send_messages=True,embed_links=True),send=AsyncMock())
        self.b.bot.get_guild=lambda _:NS(me=NS(id=99),get_channel=lambda _:channel)
        channel.send.side_effect=discord.HTTPException(NS(status=500,reason='test'),'test')
        await logs.deliver(self.b)
        self.assertEqual(self.b.db.execute('SELECT delivered FROM external_activity_log').fetchone()[0],0)
        channel.send.side_effect=None
        channel.send.return_value=NS(id=100)
        await logs.deliver(self.b)
        self.assertEqual(self.b.db.execute('SELECT delivered,log_message_id FROM external_activity_log').fetchone(),(1,100))
        self.assertFalse(channel.send.call_args.kwargs['allowed_mentions'].everyone)
        await logs.deliver(self.b)
        self.assertEqual(channel.send.await_count,2)
    async def test_missing_channel_keeps_queue(self):
        logs.capture(self.b,self.msg())
        self.b.bot.get_guild=lambda _:None
        await logs.deliver(self.b)
        self.assertEqual(self.b.db.execute('SELECT delivered FROM external_activity_log').fetchone()[0],0)

if __name__=='__main__':unittest.main()
