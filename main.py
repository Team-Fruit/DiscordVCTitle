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


# メッセージを受信し、削除する
async def ex_accept_and_delete(self: discord.Message, *, delete_delay: int=5, reaction: str='✅') -> discord.Message:
    try:
        permission: discord.Permissions = self.channel.permissions_for(self.guild.me)
        if permission.add_reactions:
            await self.add_reaction(reaction)
        if permission.manage_messages:
            await self.delete(delay=delete_delay)
    except Exception:
        pass

async def ex_deny_and_delete(self: discord.Message, *, delete_delay: int=5, reaction: str='💥'):
    await ex_accept_and_delete(self, delete_delay=delete_delay, reaction=reaction)

discord.Message.accept_and_delete = ex_accept_and_delete
discord.Message.deny_and_delete = ex_deny_and_delete


# メッセージに返信し、削除する
async def ex_reply_and_delete(self: discord.Message, content: str=None, *, embed: discord.Embed=None, delete_after: int=5) -> discord.Message:
    await self.channel.send(content, embed=embed, delete_after=delete_after)

discord.Message.reply_and_delete = ex_reply_and_delete


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
        title: Title = vclist.get(before.id)
        if title is not None:
            if title.titled_name() == after.name:
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
async def on_message(message: discord.Message):
    #処理
    await bot.process_commands(message)


# メッセージ受信時に動作する処理
@bot.command(name='title')
async def title(ctx: commands.Context, *, arg: str = 'help'):
    message: discord.Message = ctx.message

    # メッセージ送信者がBotだった場合は無視する
    if message.author.bot:
        return

    # help
    if arg == 'help':
        await message.reply_and_delete(
            embed = discord.Embed(
                title = 'ℹ️ 使い方',
                description =
                    '`/title ラベル` 参加中のVCにラベルをつける\n'
                    '`/title`、`/title help` ヘルプ\n'
                    '`/title join` ラベルの所有権を取得します\n'
                    '`/title info` ラベルの所有者を確認する\n'
                    '※VCから抜けると所有権が解放されます\n'
                    '※所有者がいなくなると名前が戻ります'
            ),
            delete_after=15
        )
        await message.accept_and_delete()
        return

    # ギルド
    guild: discord.Guild = message.guild

    if guild is None:
        await message.reply_and_delete('DMやグループチャットはサポート外です')
        await message.deny_and_delete()
        return

    # VC
    voice: discord.VoiceState = message.author.voice

    if voice is None:
        await message.reply_and_delete('VCに入ってお試しください')
        await message.deny_and_delete()
        return
        
    vc: discord.VoiceChannel = voice.channel

    if vc is None:
        await message.reply_and_delete('wtf (権限?)')
        return
    
    # 所有者チェック
    if arg == 'info' or arg == 'owner':
        # ラベルなし
        if not vc.id in vclist:
            await message.reply_and_delete(f'`{vc.name}`にラベルは作成されていません')
            await message.deny_and_delete()
            return

        # ラベル
        title: Title = vclist[vc.id]

        # 所有者リスト
        owner_list: List[str] = [f'`{owner.display_name} ({str(owner)})`' for owner in title.owners]
        owner_msg: str = '\n'.join(owner_list) if owner_list else '　なし\n※エラーによりチャンネルの復元が失敗している可能性があります。'
        if not message.author in title.owners:
            owner_msg += '\n➡️`/title join`で所有権を取得'
        await message.reply_and_delete(
            embed = discord.Embed(
                title = '👤 ラベルの所有者',
                description =
                    f'所有者: {len(title.owners)}人'
            )
            .add_field(name='チャンネル名', value=title.default_name, inline=False)
            .add_field(name='ラベル名', value=title.name, inline=False)
            .add_field(name='所有者', value=owner_msg, inline=False)
        )
        await message.accept_and_delete()

        return

    # 所有権取得
    elif arg.startswith('join'):
        # ラベルなし
        if not vc.id in vclist:
            await message.reply_and_delete(f'`{vc.name}`にラベルは作成されていません')
            await message.deny_and_delete()
            return

        # ラベル
        title: Title = vclist[vc.id]

        # 追加リスト
        add_owners: Set[discord.Member] = { message.author }
        # メンションが含まれていたらその人を追加
        if message.mentions:
            add_owners = set(message.mentions)
        
        # 参加
        member_added: bool = False
        for mention in add_owners:
            if mention in title.owners:
                if mention == message.author:
                    await message.reply_and_delete('あなたは既に参加しています')
                else:
                    await message.reply_and_delete(f'`{str(mention)}`は既にに参加しています')
            elif not mention in vc.members:
                await message.reply_and_delete(f'`{str(mention)}`はVCに参加していません')
            else:
                title.owners.add(mention)
                member_added = True
        
        if not member_added:
            await message.deny_and_delete()
            return

        await message.accept_and_delete()
        return

    else:
        # 編集
        edit: bool = False
        if arg.startswith('edit '):
            edit = True
            arg = arg[5:]

        # 名前をキャッシュ
        if not vc.id in vclist:
            # ラベルなし
            if edit:
                await message.reply_and_delete(f'`{vc.name}`にラベルは作成されていません')
                await message.deny_and_delete()
                return
            
            # 新規
            vclist[vc.id] = Title(vc.name, message.channel)
        
        # ラベル
        title: Title = vclist[vc.id]

        # もし一致していたら参加させる
        if title.name == arg:
            # 参加
            if message.author in title.owners:
                await message.reply_and_delete('あなたは既にに参加しています')
                await message.deny_and_delete()
                return
            
            title.owners.add(message.author)

            await message.accept_and_delete()
            return
        else:
            # 新しい名前
            title.name = arg
            
            # 新しい所有者
            if not edit:
                title.owners = { message.author }

            # 名前を変更
            try:
                await vc.edit(name=title.titled_name(), reason='VC Title Created')
                await message.accept_and_delete()
                return
            except discord.Forbidden as e:
                await message.reply_and_delete(f'<:terminus:451694123779489792>BotがアクセスできないVCです')
                await message.deny_and_delete()
            except discord.HTTPException as e:
                await message.reply_and_delete(f'<:terminus:451694123779489792>HTTPException: {e}')
                await message.deny_and_delete()
            except Exception as e:
                await message.reply_and_delete(f'<:terminus:451694123779489792>Exception: {e}')
                await message.deny_and_delete()


# Botの起動とDiscordサーバーへの接続
bot.run(os.environ["DISCORD_TOKEN"])
