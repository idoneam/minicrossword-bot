#!/usr/bin/env python3

import datetime
import discord
import logging
import io
import math
import os
import pytz
import sqlite3
import statistics
import subprocess
import sys
import traceback

from discord.ext import commands
from matplotlib import pyplot as plt
from matplotlib.ticker import MaxNLocator
from typing import Optional, Tuple


CMD_PREFIX = "%"
CROSSWORD_ROLE = "crosswords"
CROSSWORD_TIMEZONE = "America/New_York"
DB_PATH = "./Scoreboard.db"
DEVELOPER_ROLE = "idoneam"


# Logging configuration
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


NO_TIMES_MESSAGE = '```No times found.```'


class MiniCrosswordBot(commands.Bot):
    async def on_command_error(self, context, exception):
        tb = ""
        for line in traceback.TracebackException(type(exception), exception, exception.__traceback__)\
                .format(chain=True):
            tb += "  " + line  # Indent for logging

        logger.error("Encountered traceback:\n" + tb)


bot = MiniCrosswordBot(command_prefix=CMD_PREFIX)


def _format_time(time) -> str:
    """
    Formats total seconds into a time with minutes and padded seconds if more than 59 seconds.
    """
    if time > 59:
        m = int(math.floor(time / 60))
        s = int(time % 60)
        return f"{m}:{str(s).zfill(2)}"
    return str(int(time))


def _from_ymd(time_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(time_str, "%Y-%m-%d")


def _as_ymd(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _get_day(dt: datetime.datetime) -> str:
    return dt.strftime("%a")


def _get_day_from_ymd(time_str) -> str:
    return _get_day(_from_ymd(time_str))


@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')


@bot.command()
@commands.has_role(DEVELOPER_ROLE)
async def update(ctx):
    """
    Update the bot by pulling changes from the git repository
    """
    shell_output = subprocess.check_output("git pull", shell=True)
    status_message = shell_output.decode("unicode_escape")
    await ctx.send(f"`{status_message}`")


@bot.command()
@commands.has_role(DEVELOPER_ROLE)
async def backup(ctx):
    """
    Send the current database file to the channel
    """
    current_time = datetime.datetime.now(tz=pytz.timezone(CROSSWORD_TIMEZONE)).strftime('%Y%m%d-%H:%M')
    backup_filename = f'MiniScores_{current_time}.db'
    await ctx.send("Backup", file=discord.File(DB_PATH, filename=backup_filename))


@bot.command()
@commands.has_role(DEVELOPER_ROLE)
async def restart(ctx):
    """
    Restart the bot
    """
    await ctx.send("```Beep boop boop beep beep beep beep```")
    python = sys.executable
    os.execl(python, python, *sys.argv)


def _get_times(c: sqlite3.Cursor, member=None) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    if member:
        times_list = c.execute("SELECT Score, Date FROM Scores WHERE ID = ?", (member.id,)).fetchall()
    else:
        times_list = c.execute("SELECT Score, Date FROM Scores").fetchall()
    reg_vals = []
    sat_vals = []
    for score, score_date in times_list:
        (sat_vals if _get_day_from_ymd(score_date) == "Sat" else reg_vals).append(int(score))
    return tuple(reg_vals), tuple(sat_vals)


def _update_avg(conn: sqlite3.Connection, member) -> Tuple[Tuple[Optional[int], Optional[int]],
                                                           Tuple[Optional[int], Optional[int]]]:
    c = conn.cursor()

    reg_vals, sat_vals = _get_times(c, member)

    user_avgs = c.execute('SELECT RegAvg, SatAvg FROM Ranking WHERE ID = ?', (member.id,)).fetchone()
    if not user_avgs:
        user_avgs = (None, None)

    old_reg_avg: Optional[int]
    old_sat_avg: Optional[int]
    old_reg_avg, old_sat_avg = user_avgs

    new_reg_avg: Optional[int] = None
    new_sat_avg: Optional[int] = None

    # A regular average can only be set if regular crossword scores exist
    if reg_vals:
        new_reg_avg = int(statistics.mean(reg_vals))
        c.execute(
            "INSERT OR REPLACE INTO Ranking VALUES (:id, :name, :reg_avg, "
            "(SELECT SatAvg FROM Ranking WHERE ID=:id))",
            {"id": member.id, "name": member.name, "reg_avg": new_reg_avg}
        )
        conn.commit()

    # A saturday average can only be set if saturday crossword scores exist
    if sat_vals:
        new_sat_avg = int(statistics.mean(sat_vals))
        c.execute(
            "INSERT OR REPLACE INTO Ranking VALUES(:id, :name, (SELECT RegAvg FROM Ranking WHERE ID=:id), "
            ":sat_avg)",
            {"id": member.id, "name": member.name, "sat_avg": new_sat_avg}
        )
        conn.commit()

    # If the user has no scores, delete the average record if it exists
    if not reg_vals and not sat_vals:
        c.execute("DELETE FROM Ranking WHERE ID=?", (member.id,))
        conn.commit()

    return (old_reg_avg, new_reg_avg), (old_sat_avg, new_sat_avg)


@bot.command()
@commands.has_role(CROSSWORD_ROLE)
async def addtime(ctx, time: str = None):
    """
    Add a time to the scoreboard (use seconds in int or xx:xx format)
    """

    if not time:
        await ctx.send(f"`Use {CMD_PREFIX}help to check the correct addtime usage`")
        return

    # idiot proofing, convert time to int
    try:
        if ":" in time:
            timestamp = datetime.datetime.strptime(time, '%M:%S')
            time = timestamp.minute * 60 + timestamp.second
        else:
            time = int(time)
            if not (1 <= time <= 1000):
                raise ValueError
    except ValueError:  # Invalid strptime, int cast, or out of "valid" range
        await ctx.send('`lmao nice try ( ͠° ͟ʖ ͠°)`')
        return

    conn = sqlite3.connect(DB_PATH)

    try:
        c = conn.cursor()
        member = ctx.author

        # on weekdays, puzzle flips over at 10PMEST, on weekends 6PMEST
        datestamp = datetime.datetime.now(tz=pytz.timezone(CROSSWORD_TIMEZONE))
        if (_get_day(datestamp) in ("Sat", "Sun") and datestamp.hour >= 18) or datestamp.hour >= 22:
            datestamp = datestamp + datetime.timedelta(days=1)

        day = _get_day(datestamp)

        c.execute("INSERT OR REPLACE INTO Scores VALUES (?, ?, ?, ?)",
                  (member.id, member.name, _as_ymd(datestamp), time))
        conn.commit()
        await ctx.send("```css\nScore added.\n```")

        # Update averages and attach them to the message

        def _format_avg_delta(ad):
            return f" [{ad}]" if ad else ""

        def _avg_text(old_avg: Optional[int], new_avg: Optional[int], saturday: bool = False) -> str:
            if not new_avg:
                return ""

            right_day_for_average = (day != "Sat" and not saturday) or (day == "Sat" and saturday)

            avg_diff = f"{new_avg - old_avg:+d}" if old_avg is not None and right_day_for_average else None

            return f"~ {member.name}'s {'Saturday' if saturday else 'Regular'} Crossword Avg: " \
                   f"{_format_time(new_avg)}{_format_avg_delta(avg_diff)} ~"

        (old_reg_avg, new_reg_avg), (old_sat_avg, new_sat_avg) = _update_avg(conn, member)
        msg = f"```{_avg_text(old_reg_avg, new_reg_avg)}\n{_avg_text(old_sat_avg, new_sat_avg, saturday=True)}```"
        await ctx.send(msg)

    finally:
        conn.close()


@bot.command()
@commands.has_role(CROSSWORD_ROLE)
async def ltimes(ctx):
    """
    List your 20 most recent scores
    """

    conn = sqlite3.connect(DB_PATH)

    try:
        c = conn.cursor()
        times_list = c.execute("SELECT Score,Date FROM Scores WHERE ID=? ORDER BY Date DESC",
                               (ctx.author.id,)).fetchall()
        if not times_list:
            await ctx.send(NO_TIMES_MESSAGE)
            return

        scores_str = "\n".join(f"({score_date}) {_format_time(score)}" for score, score_date in times_list[:20])
        await ctx.send(f"```{ctx.author.name}'s Scoreboard: \n{scores_str}\n```")

    finally:
        conn.close()


@bot.command()
@commands.has_role(CROSSWORD_ROLE)
async def useravg(ctx):
    """
    List your Saturday crossword avg and your regular avg
    """

    conn = sqlite3.connect(DB_PATH)

    try:
        c = conn.cursor()

        avgslist = c.execute('SELECT RegAvg, SatAvg FROM Ranking WHERE ID=?', (ctx.author.id,)).fetchall()
        if not avgslist:
            await ctx.send("```This user doesn't have any times yet.```")
            return

        reg_avg, sat_avg = avgslist[0]

        def _format_avg(sat: bool):
            avg = sat_avg if sat else reg_avg
            return f"~ {ctx.author.name}'s {'Saturday' if sat else 'Regular'} Crossword Avg: " \
                   f"{_format_time(avg)}\n" if avg else ""

        await ctx.send(f"```apache\n{_format_avg(False)}{_format_avg(True)}```")

    finally:
        conn.close()


async def _rank(ctx, saturday: bool = False):
    conn = sqlite3.connect(DB_PATH)

    try:
        c = conn.cursor()

        times = c.execute(f"SELECT Name, {'SatAvg' if saturday else 'RegAvg'} FROM Ranking").fetchall()
        if not times:
            await ctx.send(f"```No one has any {'' if saturday else 'non-'}Saturday crossword scores yet.```")
            return

        await ctx.send(f"```css\n{'Saturday ' if saturday else ''}Minicrossword Scoreboard:\n```")

        scoreboard = []

        # times is a list of tuples of (member name, avg time)
        for member_name, avg in sorted(filter(lambda t: t[1] is not None, times), key=lambda t: t[1]):
            if len(scoreboard) == 10:
                break

            usr_times_list = c.execute('SELECT Score, Date FROM Scores WHERE Name=? ORDER BY Date',
                                       (member_name,)).fetchall()
            type_days = ["", *(
                score_date
                for _, score_date in usr_times_list
                if (saturday and _get_day_from_ymd(score_date) == "Sat") or
                   (not saturday and _get_day_from_ymd(score_date) != "Sat")
            )]

            delta = datetime.datetime.now() - datetime.datetime.strptime(type_days[-1], '%Y-%m-%d')
            if delta.days > (30 if saturday else 10):
                continue

            scoreboard.append(f"[{len(scoreboard) + 1}] {member_name}: {_format_time(avg)} (of {len(type_days) - 1})")

        scoreboard_str = "\n".join(scoreboard)
        if scoreboard_str:  # Don't bother sending if it's blank
            await ctx.send(f"```{scoreboard_str}```")

    finally:
        conn.close()


@bot.command()
@commands.has_role(CROSSWORD_ROLE)
async def rank(ctx):
    """
    Display the top 10 in the scoreboard
    """
    await _rank(ctx, saturday=False)


@bot.command()
@commands.has_role(CROSSWORD_ROLE)
async def saturdayrank(ctx):
    """
    Display the top 10 in the Saturday minicrossword scoreboard
    """
    await _rank(ctx, saturday=True)


async def _hist(ctx, saturday: bool = False):
    conn = sqlite3.connect(DB_PATH)

    try:
        c = conn.cursor()

        all_scores = _get_times(c)[int(saturday)]
        scores = _get_times(c, ctx.author)[int(saturday)]

        if not (all_scores and scores):
            await ctx.send(NO_TIMES_MESSAGE)
            return

        bins = tuple(range(30, 185, 5)) if saturday else tuple(range(10, 165, 5))

        fig, ax = plt.subplots(nrows=1, ncols=1)
        ax.set_title(f"{ctx.author.name}'s {'saturday ' if saturday else ''}score histogram",
                     color="#DCDDDE")
        ax.set_facecolor("#40444B")
        ax.hist(all_scores, bins, density=True, color="#942626")
        ax.hist(scores, bins, density=True, color="#F04747")
        fig.legend(
            ("everyone", ctx.author.name),
            bbox_to_anchor=(0.92, 0.034),
            loc="lower right",
            ncol=2,
            labelcolor="#DCDDDE",
            fancybox=False,
            framealpha=0)
        fig.subplots_adjust(bottom=0.15)
        ax.axvline(statistics.mean(all_scores), color="#BB3030", linestyle="dashed", linewidth=2)
        ax.axvline(statistics.mean(scores), color="#F47676", linestyle="dashed", linewidth=2)
        ax.set_xlabel("time (seconds)", color="#DCDDDE", loc="left")
        ax.set_ylabel("density", color="#DCDDDE")
        ax.tick_params(axis="x", colors="#DCDDDE")
        ax.tick_params(axis="y", colors="#DCDDDE")

        with io.BytesIO() as tf:
            fig.savefig(tf, dpi=300, facecolor="#2F3136", edgecolor="#2F292B")  # defaults to PNG
            tf.seek(0)
            await ctx.send(file=discord.File(tf, filename="hist.png"))

    finally:
        conn.close()


@bot.command()
@commands.has_role(CROSSWORD_ROLE)
async def hist(ctx):
    """
    Displays a histogram of user scores for the normal crossword
    """
    await _hist(ctx, saturday=False)


@bot.command()
@commands.has_role(CROSSWORD_ROLE)
async def sathist(ctx):
    """
    Displays a histogram of user scores for the Saturday crossword
    """
    await _hist(ctx, saturday=True)


@bot.command()
@commands.has_role(CROSSWORD_ROLE)
async def deltime(ctx):
    """
    Delete a specific time from your scoresheet. Use if you made a mistake entering something in (it's based on an
    honour system).
    """

    conn = sqlite3.connect(DB_PATH)

    try:
        c = conn.cursor()
        times_list = c.execute('SELECT Score, Date FROM Scores WHERE ID = ?', (ctx.author.id,)).fetchall()
        if not times_list:
            await ctx.send('```No scores found.```')
            return

        # print the times of the user in pages
        msg = "```Please choose a score you would like to delete.\n\n"
        for i, (score, score_date) in enumerate(times_list, 1):
            msg += f'[{i}]  ({score_date}) {_format_time(score)} \n'
        msg += '```'
        await ctx.send(msg, delete_after=30)
        msg = '```\n[0] Exit without deleting scores```'
        await ctx.send(msg, delete_after=30)

        def event_check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        response = await ctx.bot.wait_for("message", check=event_check)
        choice = int(response.content)
        is_valid_choice = 0 <= choice <= (1 + len(times_list))

        if not is_valid_choice:
            await ctx.send("```Invalid input.```")
            return

        if choice == 0:
            await ctx.send("```Exited score deletion menu.```")
            return

        # Delete selected the score from the database
        c.execute('DELETE FROM Scores WHERE Score=? AND Date=? AND ID=?',
                  (times_list[choice - 1][0], times_list[choice - 1][1], ctx.author.id))
        conn.commit()

        # Update average scores in the database
        _update_avg(conn, ctx.author)

        await ctx.send("```Score successfully deleted.```")

    finally:
        conn.close()


@bot.command()
async def link(ctx):
    await ctx.send("https://www.nytimes.com/crosswords/game/mini")


def main():
    # Create the database with the required tables if needed
    with open("./schema.sql", "r") as sf:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.executescript(sf.read())
        conn.close()

    # Start the bot
    bot.run(os.environ.get("DISCORD_TOKEN"))


if __name__ == "__main__":
    main()
