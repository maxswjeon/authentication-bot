import os
import random
import sqlite3
import string
import subprocess
import time

import discord
import dotenv
import sshpubkeys
from discord.ext import commands


def generate_temp_file(length=10):
    file_path = 'temp/' + str(time.time_ns())
    string_pool = string.printable
    for i in range(length):
        file_path += random.choice(string_pool)

    return file_path


def main():
    intents = discord.Intents.default()
    intents.members = True

    channels = os.getenv('DISCORD_CHANNELS').split(',')
    channels = list(filter(lambda x: x.strip(), channels))

    command_help = commands.DefaultHelpCommand(
        no_category='Commands'
    )

    bot = commands.Bot(
        command_prefix='/',
        description='Server Authentication Bot',
        intents=intents,
        help_command=command_help
    )

    database = sqlite3.connect(os.getenv('DATABASE_PATH'))

    @bot.command(brief='Generate Certificate for SSH Login')
    async def authorize(ctx: commands.Context, *, public_key: str):
        try:
            key_data = sshpubkeys.SSHKey(public_key, strict=True)
            key_data.parse()
        except sshpubkeys.InvalidKeyError:
            await ctx.send('Invalid Public Key', delete_after=10.0)
            return
        except NotImplementedError:
            await ctx.send('Invalid Public Key', delete_after=10.0)
            return

        if os.getenv('ENFORCE_STRONG_KEYS') == 'True':
            if key_data.key_type not in [b'ssh-rsa', b'ssh-ed25519']:
                await ctx.send('Weak Key. Only RSA Keys over 2048 bits and ED25519 Keys are supported',
                               delete_after=10.0)
                return

            if key_data.key_type == b'ssh-rsa' and key_data.bits < 2048:
                await ctx.send('Weak Key. Only RSA Keys over 2048 bits and ED25519 Keys are supported',
                               delete_after=10.0)
                return

        cursor = database.cursor()
        keys = cursor.execute(f'SELECT key FROM user_keys WHERE user = {ctx.author.id};')
        exist = False
        key_index = 0
        for key in keys:
            if key[0] == public_key:
                exist = True
                break
            key_index += 1

        if not exist:
            cursor.execute(f'INSERT INTO user_keys(user, key) VALUES (?, ?)', (ctx.author.id, public_key))
            database.commit()

        temp_path = generate_temp_file()
        with open(temp_path, "w") as f:
            f.write(public_key)

        user = ctx.author.split('#')[0]
        cert = subprocess.check_output(['ssh-keygen',
                                        '-s', 'ca_user_key',
                                        '-l', f'{user}#{key_index}',
                                        '-n', f'ubuntu,{user}',
                                        '-V', f'+{os.getenv("CERTIFICATE_VALID_DAYS") or 7}d',
                                        temp_path])
        os.remove(temp_path)
        await ctx.send(cert, delete_after=30.0)

    @bot.command(brief='Revoke Exposed, Stolen Key')
    async def revoke(ctx: commands.Context, key_index: int):
        cursor = database.cursor()
        public_key = cursor.execute(f'SELECT key FROM user_keys WHERE id = {key_index}').fetchone()[0]

        try:
            key_data = sshpubkeys.SSHKey(public_key, strict=True)
            key_data.parse()
        except sshpubkeys.InvalidKeyError:
            await ctx.send('Unknown Error Occurred', delete_after=10)
            return

        with open('revoked_keys', 'a') as f:
            f.write(public_key)
            f.write('\n')

        cursor.execute(f'DELETE FROM user_keys WHERE id = {key_index}')
        await ctx.send(f'Revoked Key : `{public_key[:50]}... ({key_data.comment})`', delete_after=10)

    @bot.command(brief='List Keys Authorized Before')
    async def manage(ctx: commands.Context):
        cursor = database.cursor()
        key_list = ''
        keys = cursor.execute(f'SELECT id, key FROM user_keys WHERE user = {ctx.author.id} ORDER BY id;').fetchall()
        for (key_id, key) in keys:
            try:
                key_data = sshpubkeys.SSHKey(key, strict=True)
                key_data.parse()
            except sshpubkeys.InvalidKeyError:
                continue

            key_list += f'{key_id}: {key[:50]}... ({key_data.comment})\n'

        if key_list == '':
            await ctx.send('There is No Authorized Key exists from user')
            return

        await ctx.send(key_list, delete_after=30.0)

    @bot.command(brief='Delete Messages from Bot')
    async def clear(ctx: commands.Context):
        print('Command: /clear')
        await ctx.channel.purge(limit=100, check=lambda m: m.author == bot.user)
        await ctx.message.add_reaction('\U0001F44D')

    @bot.event
    async def on_ready():
        print(f'Logged in as {bot.user.name} ({bot.user.id})')

    @bot.event
    async def on_message(message: discord.Message):
        if str(message.channel.id) not in channels:
            return
        await bot.process_commands(message)

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        print(f'Error : {error}')

        error = getattr(error, 'original', error)

        if isinstance(error, commands.MissingRequiredArgument):
            message = await ctx.send('Missing Required Argument')
            await message.delete(delay=10)

    bot.run(os.getenv('BOT_TOKEN'))


if __name__ == '__main__':
    dotenv.load_dotenv()
    main()
