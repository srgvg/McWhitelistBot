import os
import discord
from discord.ext import commands
from mcrcon import MCRcon

from modules import *
import modules

import logging
logging_level = os.getenv('logging_level')
level = logging.getLevelName(logging_level)
logging.basicConfig(level=level,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

bot = commands.Bot(command_prefix='.')
bot_token = os.getenv('bot_token')
server_ip = os.getenv('server_ip')
mc_version = os.getenv('mc_version')
mcrcon_secret = os.getenv('mcrcon_secret')

requests_messages = []


def mcrcon_command(command):
    if mcrcon_secret is not None:
        with MCRcon(server_ip, mcrcon_secret) as mcr:
            response = mcr.command(command)
            logging.info('Sent command "{}" to server "{}" and got reponse "{}"'.format(command, server_ip, response))
            return response

def take_request(message_id):
    for i in requests_messages:
        if i.admin_msg_id == message_id:
            tmp = i
            requests_messages.remove(i)
            return tmp


@bot.event
async def on_ready():
    logging.info('Ready, username: {}'.format(bot.user.name))
    await bot.change_presence(activity=discord.Game('Minecraft'), status=discord.Status.online)
    # TODO: Read pending requests out of file


@bot.event
async def on_disconnect():
    modules.filemanager.save_requests(requests_messages)


@bot.event
async def on_raw_reaction_add(payload):
    channel = await bot.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    user = await bot.fetch_user(payload.user_id)
    if not user.bot:
        msg = message
        if msg.author == bot.user:
            admin = user
            current = take_request(msg.id)
            await msg.delete()
            if type(current) == request.WhitelistRequest:
                mc_name = current.mc_name
                dc_user = await bot.fetch_user(current.author_id)
                logging.info('Got WhitelistRequest, emoji reaction: "{}"'.format(payload.emoji))
                if str(payload.emoji) == '✅':
                    logging.info('Got ✅ reaction.')
                    uuid = current.uuid
                    await modules.filemanager.write_whitelist(mc_name, uuid)
                    mcrcon_command("/whitelist add {}".format(mc_name))
                    logging.info('Player whitelisted: {} {}'.format(mc_name, uuid))
                    embed = discord.Embed(title='Server', color=0x22a7f0)
                    embed.add_field(name='IP', value=server_ip)
                    embed.add_field(name='Version', value=mc_version)
                    await dc_user.send(
                        'Your request for the player  `{}` was accepted. It may take up to 5 more minutes'
                        ' until you will be able to join the server.'.format(mc_name),
                        embed=embed)
                    await admin.send('The player `{}` was whitelisted.'.format(mc_name))
                    logging.info('The player `{}` was whitelisted.'.format(mc_name))
                else:
                    await admin.send('The request for the player `{}` was denied.'.format(mc_name))
                    await dc_user.send('Your request for the player `{}`was denied.'.format(mc_name))
                    logging.info('The request for the player `{}` was denied.'.format(mc_name))


@bot.command()
async def whitelist(ctx, arg):
    mc_name = arg
    member = ctx.author
    logging.info('Got whitelist request for {}, from {}'.format(mc_name,
                                                                member.mention))
    await ctx.message.delete()
    logging.info('Checking if Admin defined...')
    if not modules.filemanager.get_admin_id(member.guild.id):
        await ctx.send('Fatal Error: No admin defined for this server.')
        return
    logging.info('Fetching admin ID...')
    admin_id = modules.filemanager.get_admin_id(member.guild.id)
    logging.info('Fetching admin user...')
    admin = await bot.fetch_user(admin_id)
    logging.info('Got admin user {} admin')
    logging.info('Fetching UUID for user {} ...'.format(mc_name))
    uuid = util.get_uuid(mc_name)
    logging.info('Got UUID {}'.format(uuid))
    if not uuid:
        logging.info('Player `{}` not found {}.'.format(mc_name, member.mention))
        await ctx.send('Player `{}` not found {}.'.format(mc_name, member.mention))
        return
    else:
        logging.info('Player `{}` was found {}.'.format(mc_name, member.mention))
        await ctx.send('Player `{}` was found {}.'.format(mc_name, member.mention))
    embed = discord.Embed(title='Whitelist request', color=0x22a7f0)
    embed.add_field(name='by', value=ctx.author.mention)
    embed.add_field(name='MC-Username', value=mc_name)
    embed.add_field(name='joined server', value=member.joined_at.strftime('%d.%m.%Y, %H:%M'))
    admin_msg = await admin.send(embed=embed)
    await admin_msg.add_reaction('✅')
    await admin_msg.add_reaction('❌')
    requests_messages.append(request.WhitelistRequest(ctx.author.id, admin_msg.id, mc_name, uuid))
    await ctx.send('Your request for whitelisting `{}` was sent {}.'.format(mc_name, member.mention))
    logging.info('Your request for whitelisting `{}` was sent {}.'.format(mc_name, member.mention))


@bot.command()
async def imtheadmin(ctx):
    author = ctx.message.author
    guild_id = ctx.message.guild.id
    await ctx.message.delete()
    old_admin_id = modules.filemanager.get_admin_id(guild_id)
    if old_admin_id:
        old_admin = await bot.fetch_user(old_admin_id)
        embed = discord.Embed(title='Admin request')
        embed.add_field(name='by', value=author.mention)
        embed.add_field(name='joined server', value=author.joined_at.strftime('%d.%m.%Y, %H:%M'))
        admin_msg = await old_admin.send(embed=embed)
        requests_messages.append(request.Request(author.id, admin_msg.id))
        await admin_msg.add_reaction('✅')
        await admin_msg.add_reaction('❌')
        await ctx.send('Your request for administration privileges was sent to an existing admin. ' + author.mention)
        logging.info('Your request for administration privileges was sent to an existing admin. ' + author.mention)
    else:
        modules.filemanager.add_admin(author.id, guild_id)
        logging.info('Your request for administration privileges was processed. ')


@whitelist.error
async def whitelist_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Please use .whitelist [Minecraft username].')


bot.run(bot_token)
