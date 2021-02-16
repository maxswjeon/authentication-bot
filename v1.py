import os
import random
import sqlite3
import string
import subprocess
import time

import discord
import dotenv
import sshpubkeys


class CertificateBot(discord.Client):
    def __init__(self):
        super().__init__()
        self.database = sqlite3.connect(os.getenv('DATABASE_PATH'))

    async def on_ready(self):
        print(f'Logged as \"{self.user}\"')

    async def on_message(self, message: discord.Message):
        print(message.author)
        if message.author == self.user:
            return

        command: str = message.content.strip()

        if command is None or command[0] != '/':
            return

        if command.startswith('/authorize'):
            await self.authorize(message, command)
            return

        if command.startswith('/revoke'):
            await message.channel.send('Pending Implementation...', delete_after=10.0)
            return

        if command.startswith('/manage'):
            await self.manage(message)
            return

        if command.startswith('/clear'):
            await message.channel.purge(limit=100, check=self.is_me)
            await message.add_reaction('\U0001F44D')
            return

        if command.startswith('/help'):
            await message.channel.send('''
SSH Key Management Bot

Usage:
`/authorize [public_key]`
    public_key: OpenSSH Format Public Key
    Authorize Key and Create Key Certificate (starts with `sha-rsa` or `sha-ed25519`)
    
`/revoke [key_index]`
    key_index: run /manage to find key index
    Revoke key when key is exposed, leaked, or lost

`/manage`
    Manage keys authorized before

`/clear`
    Remove all bot-generated messages

`/help`
    Show this message
                                       ''', delete_after=30.0)
            return

    async def authorize(self, message: discord.Message, command: str):
        if command.find(' ') == -1:
            await message.channel.send('Usage: /authorize [public_key]\n'
                                       '\tpublic_key: OpenSSH Format Public Key '
                                       '(starts with `sha-rsa` or `sha-ed25519`)',
                                       delete_after=10.0)
            return

        public_key = command[command.find(' ') + 1:]
        try:
            ssh_pubkey = sshpubkeys.SSHKey(public_key, strict=True)
            ssh_pubkey.parse()
        except sshpubkeys.InvalidKeyError:
            await message.channel.send('Invalid Public Key', delete_after=10.0)
            return
        except NotImplementedError:
            await message.channel.send('Invalid Public Key', delete_after=10.0)
            return

        if ssh_pubkey.key_type not in [b'ssh-rsa', b'ssh-ed25519']:
            await message.channel.send('Weak Key. Only RSA Keys over 2048 bits and ED25519 Keys are supported',
                                       delete_after=10.0)
            return

        if ssh_pubkey.key_type == b'ssh-rsa' and ssh_pubkey.bits < 2048:
            await message.channel.send('Weak Key. Only RSA Keys over 2048 bits and ED25519 Keys are supported',
                                       delete_after=10.0)
            return

        cursor = self.database.cursor()
        keys = cursor.execute(f'SELECT key FROM user_keys WHERE user = {message.author.id};')
        exist = False
        key_index = 0
        for key in keys:
            if key[0] == public_key:
                exist = True
                break
            key_index += 1

        if not exist:
            cursor.execute(f'INSERT INTO user_keys(user, key) VALUES (?, ?)', (message.author.id, public_key))
            self.database.commit()

        temp_path = self.generate_temp_file()
        with open(temp_path, "w") as f:
            f.write(public_key)

        user = message.author.split('#')[0]
        cert = subprocess.check_output(['ssh-keygen',
                                        '-s', 'ca_user_key',
                                        '-l', f'{user}#{key_index}',
                                        '-n', f'ubuntu,{user}',
                                        '-V', '+1w',
                                        temp_path])
        os.remove(temp_path)
        await message.channel.send(cert, delete_after=30.0)

    async def manage(self, message: discord.Message):
        cursor = self.database.cursor()
        key_list = ''
        keys = cursor.execute(f'SELECT id, key FROM user_keys WHERE user = {message.author.id} ORDER BY id;')
        index = 0
        for key in keys:
            try:
                ssh_pubkey = sshpubkeys.SSHKey(key[0], strict=True)
                ssh_pubkey.parse()
            except sshpubkeys.InvalidKeyError:
                continue

            key_list += f'{index}. {key[0][:50]}... ({ssh_pubkey.comment})\n'
            index += 1
        await message.channel.send(key_list, delete_after=30.0)

    async def revoke(self, message: discord.Message):
        command = message.content.strip()
        if len(command.split(' ')) != 2:
            await message.channel.send('Usage: /revoke [key_index]\n'
                                       '\tkey_index: run /manage to find key index', delete_after=10.0)
            return

    def is_me(self, message):
        return message.author == self.user

    @staticmethod
    def generate_temp_file(length=10):
        file_path = 'temp/' + str(time.time_ns())
        string_pool = string.printable
        for i in range(length):
            file_path += random.choice(string_pool)

        return file_path


def main():
    if not os.path.exists(os.getenv('DATABASE_PATH')):
        database = sqlite3.connect(os.getenv('DATABASE_PATH'))
        database.execute('create table user_keys ('
                         'id integer not null constraint user_keys_pk primary key autoincrement, '
                         'user integer not null, '
                         'key text not null'
                         ');')
        database.execute('create unique index user_keys_id_uindex on user_keys (id);')
        database.commit()
        database.close()

    bot = CertificateBot()
    bot.run(os.getenv('BOT_TOKEN'))


if __name__ == "__main__":
    dotenv.load_dotenv()
    main()
