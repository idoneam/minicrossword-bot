# minicrossword-bot

A Discord bot that keeps track of user-submitted scores for the
[NYT Mini Crossword](https://www.nytimes.com/crosswords/game/mini)
in an embedded SQLite database.


Supports users adding their times, displaying most recent times, deleting times,
displaying user averages, and displaying rankings for the more difficult Saturday
crosswords and the regular ones.


## Setup for Development

### Pre-requisites

* git
* Python 3.7 or higher
* [`virtualenv`](https://pypi.org/project/virtualenv/)
* A valid Discord bot token ([instructions](https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token))

### Installation

```bash
# Clone the repository
git clone https://github.com/idoneam/minicrossword-bot.git && cd minicrossword-bot

# Set up a virtualenv named `env`
python -m virtualenv env

# Activate the virtual environment (just run env/bin/activate, without the source prefix on Windows)
source env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up pre-commit hook
pre-commit install

# Create .env file from .env.example
cp .env.example .env
```

After your `.env` file is created, add your Discord bot token in the `DISCORD_TOKEN`
environment variable:

```text
DISCORD_TOKEN=####################
```

### Running the bot

Start up the main Python file:
```bash
# Activate the virtual environment (just run env/bin/activate, without the source prefix on Windows)
source env/bin/activate

# Run bot
python Main.py
```

As long as the process is running, the bot will listen to commands on your Discord
server.

In addition to the user-facing commands outlined above, there are developer commands
available to users with the `idoneam` role. See [`Main.py`](./Main.py) docstrings for additional
details.


## Deploying

The bot should be deployed using the provided Dockerfile.

The image can be built with the following command:

```bash
docker build -t minicrossword:latest .
```

To run the container in a detached state with a persistent volume for the database, use
one of the following commands:

```bash
# Provide the bot's token using a flag:
docker run \
  -v $(pwd)/Scoreboard.db:/bot/Scoreboard.db \
  -e DISCORD_TOKEN=...

# Provide the bot's token using a .env file provided at runtime:
#   Note that this uses Docker's built-in --env-file flag, but the .env file can also
#   be bound to the container, in which case python-dotenv will load it instead.
docker run \
  -v $(pwd)/Scoreboard.db:/bot/Scoreboard.db \
  --env-file $(pwd)/.env 
```
