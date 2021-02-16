import os
from typing import List

import discord
import dotenv


def main():
    bot = discord.Client()

    @bot.event
    async def on_connect():
        guilds: List[discord.Guild] = bot.guilds
        for guild in guilds:
            print(guild.name)
            for channel in guild.channels:
                if type(channel) != discord.TextChannel:
                    continue

                channel: discord.TextChannel = channel
                print(f'\t{channel.name} ({channel.id})')
            print()

        await bot.close()

    bot.run(os.getenv('BOT_TOKEN'))


if __name__ == '__main__':
    dotenv.load_dotenv()

    # py_ver = int(f"{sys.version_info.major}{sys.version_info.minor}")
    # if py_ver > 37 and sys.platform.startswith('win'):
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    main()
