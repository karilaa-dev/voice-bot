# VoiceMaster

Discord bot created to change the way servers run, instead of having permanent channels you can now create temporary ones that delete themselves once they are empty.

Originally I developed this bot with a small scale in mind as it was only meant to be used in my Discord server at the time, as time went on I decided to release it to the public and make the bot public so that everyone could benefit from it.

Since it was only meant to be used for my personal server I didn't write it very efficiently or very scalable which caused many issues down the line, sqlite really limits the bot as it suggests in the title Lite, it's not meant for big scale development with lots of requests.

So after the bot started growing I decided to rewrite it from scratch and make it a lot more efficient and re write the database structure and start using Postgresql and Asyncpg to deal with the database stuff.

The code on this repository is very old but still functional I will keep it functional and update any breaking changes done to Discord or Discord.py so that everyone can benefit from it.

I released the source code so that it might be some help to developers maybe teach them or just simply allow users to host their own version.

I won't be releasing any new updates and won't be releasing the new source code, I have discontinued any updates and won't be helping people with hosting it there are Discord servers that will deal with that.

Looking for a reliable and cheap host? This isn't a sponsor or anything just an honest recommendation.
GalaxyGate is my go to when it comes to hosting Discord bots or anything that requires hosting, they have brilliant support.
I'll leave my affliate link here if you wish to purchase a vps, it'd help me pay for VoiceMaster and help you find a suitable hosting service.
https://billing.galaxygate.net/aff.php?aff=131

Python Discord server:
https://discord.gg/python

Discord.py Discord server:
https://discord.gg/dpy

Our discord server:
https://discord.gg/y9pgpbt

Use our public bot:
https://voicemaster.xyz/

**This version of the bot is sufficient enough for casual use on afew servers, I have no intention what so ever of updating it nor will support anyone with hosting it.**

**I won't be releasing the new version of the bots source code either so don't ask.**

# How to setup the bot:

1.Download python using the following link:

	https://www.python.org/downloads/

2.Clone the bot from GitHub

3.Open terminal and follow these steps:

	Change directory to this folder and Type:

	`pip3 install -r requirements.txt`

4.Set the following environment variables:
	- `DISCORD_TOKEN`: Your bot's token.
	- `COMMAND_PREFIX`: The command prefix (default is `.`).
	- `ADMIN_ID`: The ID of the bot admin (default is the original author's ID).

5.Run the bot:
	`python3 voicecreate.py`

# Docker Support

You can also run this bot using Docker. This is recommended for easier deployment and management.

## Using Docker Compose (Recommended)

1.  Clone the repository.
2.  Create a `.env` file in the root directory with the following content:

    ```env
    DISCORD_TOKEN=your_discord_token_here
    ADMIN_ID=your_admin_id_here
    COMMAND_PREFIX=.
    ```

3.  Run the bot:

    ```bash
    docker-compose up -d
    ```

    The bot will start in the background. The database will be persisted in the `./data` directory.

## Using Docker Run

If you prefer not to use Docker Compose, you can run the container directly.

1.  Build the image:

    ```bash
    docker build -t voicemaster .
    ```

2.  Run the container:

    ```bash
    docker run -d \
      --name voice-bot \
      -v $(pwd)/data:/app/data \
      -e DISCORD_TOKEN=your_discord_token_here \
      -e ADMIN_ID=your_admin_id_here \
      -e COMMAND_PREFIX=. \
      -e DB_PATH=/app/data/voice.db \
      voicemaster
    ```

    Make sure to replace `your_discord_token_here` and `your_admin_id_here` with your actual values.
