# discord.py
import discord
import re
import os
from typing import List
from typing import Set
from typing import Dict
from discord.ext import commands


# 接続に必要なオブジェクトを生成
bot = commands.Bot(command_prefix='/')


# ラベル
class Title:
    default_symbol: str
    default_name: str
    default_request_channel: discord.channel.TextChannel
    name: str = None
    owners: Set[discord.Member] = set()

    def __init__(self, name: str, request_channel: discord.channel.TextChannel):
        self.default_symbol = name[0]
        self.default_name = name
        self.default_request_channel = request_channel

    def titled_name(self) -> str:
        return f'{self.default_symbol}{self.name}'


# ラベルデータベース
vclist: Dict[int, Title] = {}


# 起動時に動作する処理
@bot.event
async def on_ready():
    # 起動したらターミナルにログイン通知が表示される
    print('ログインしました')


# VCが消えたときの処理
@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    # キャッシュ削除
    vclist.pop(channel.id, None)


# VCの名前が変更されたときの処理
@bot.event
async def on_guild_channel_update(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    # 名前の変更
    if before.name == after.name:
        return

    # Botによる操作を無視
    if before.id in vclist:
        return

    # キャッシュ削除
    vclist.pop(before.id, None)


# VCのメンバー移動時の処理
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # 移動元のVCのラベル所有権を削除

    # チャンネル移動は除外
    if before.channel == after.channel:
        return

    # 新規参加は除外
    if before is None:
        return

    vc: discord.VoiceChannel = before.channel

    if vc is None:
        return
        
    # ラベル
    title: Title = vclist.get(vc.id)

    if title is None:
        return

    # 所有権削除
    title.owners.discard(member)

    # 所有権ゼロチェック
    if not title.owners:
        # ラベル削除
        channel: discord.channel.TextChannel = title.default_request_channel
        error_msg: str = f'<:terminus:451694123779489792>`{vc.name}`→`{title.default_name}`チャンネルの復元失敗'

        # 名前を戻す
        try:
            await vc.edit(name=title.default_name, reason='VC Title Removed')
            # キャッシュ削除
            vclist.pop(vc.id, None)
        except discord.Forbidden as e:
            await channel.send(f'{error_msg}: BotがアクセスできないVCです')
        except discord.HTTPException as e:
            await channel.send(f'{error_msg}: HTTPException: {e}')
        except Exception as e:
            await channel.send(f'{error_msg}: Exception: {e}')


# メッセージ
@bot.event
async def on_message(message):
    #処理
    await bot.process_commands(message)


# メッセージ受信時に動作する処理
@bot.command(name='title')
async def title(ctx: commands.Context, arg: str = 'join'):
    message: discord.Message = ctx.message

    # メッセージ送信者がBotだった場合は無視する
    if message.author.bot:
        return

    # help
    if arg == 'help':
        await message.channel.send(
            embed = discord.Embed(
                title = 'ℹ️ 使い方',
                description =
                    '`/title ラベル` 参加中のVCにラベルをつける\n'
                    '`/title` ラベルの所有権を取得します\n'
                    '`/title join` ラベルの所有権を取得します\n'
                    '`/title owner` ラベルの所有者を確認する\n'
                    '※VCから抜けると所有権が解放されます\n'
                    '※所有者がいなくなると名前が戻ります'
            )
        )
        return

    # ギルド
    guild: discord.Guild = message.guild

    if guild is None:
        await message.channel.send('DMやグループチャットはサポート外です')
        return

    # VC
    voice: discord.VoiceState = message.author.voice

    if voice is None:
        await message.channel.send('VCに入ってお試しください')
        return
        
    vc: discord.VoiceChannel = voice.channel

    if vc is None:
        await message.channel.send('wtf (権限?)')
        return
    
    # 所有者チェック
    if arg == 'owner':
        # ラベルなし
        if not vc.id in vclist:
            await message.channel.send('VCにラベルは作成されていません')
            return

        # ラベル
        title: Title = vclist[vc.id]

        # 所有者リスト
        owner_list: List[str] = [f'　`{owner.display_name} ({str(owner)})`' for owner in title.owners]
        owner_msg: str = '\n'.join(owner_list) if owner_list else '　なし\n※エラーによりチャンネルの復元が失敗している可能性があります。'
        await message.channel.send(f'`{vc.name}`のラベルの所有者:\n{owner_msg}')

        return

    # 所有権取得
    elif arg == 'join':
        # ラベルなし
        if not vc.id in vclist:
            await message.channel.send('VCにラベルは作成されていません')
            return

        # ラベル
        title: Title = vclist[vc.id]

        # 参加
        if message.author in title.owners:
            await message.channel.send('既にに参加しています')
            return
        
        title.owners.add(message.author)

        try:
            if guild.me.guild_permissions.manage_messages:
                await message.delete()
        except Exception as e:
            pass

        return

    else:
        # 名前をキャッシュ
        if not vc.id in vclist:
            vclist[vc.id] = Title(vc.name, message.channel)
        
        # ラベル
        title: Title = vclist[vc.id]

        # もし一致していたら参加させる
        if title.name == arg:
            # 参加
            if message.author in title.owners:
                await message.channel.send('既にに参加しています')
                return
            
            title.owners.add(message.author)

            try:
                if guild.me.guild_permissions.manage_messages:
                    await message.delete()
            except Exception as e:
                pass

            return
        else:
            # 新しい名前
            title.name = arg
            
            # 新しい所有者
            title.owners = { message.author }

            # 名前を変更
            try:
                await vc.edit(name=title.titled_name(), reason='VC Title Created')
                if guild.me.guild_permissions.manage_messages:
                    await message.delete()
            except discord.Forbidden as e:
                await message.channel.send(f'<:terminus:451694123779489792>BotがアクセスできないVCです')
            except discord.HTTPException as e:
                await message.channel.send(f'<:terminus:451694123779489792>HTTPException: {e}')
            except Exception as e:
                await message.channel.send(f'<:terminus:451694123779489792>Exception: {e}')

            return


# Botの起動とDiscordサーバーへの接続
bot.run(os.environ["DISCORD_TOKEN"])
