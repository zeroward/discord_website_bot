from datetime import datetime, timedelta
import discord
from discord.ext import commands
from discord.ext import tasks
import json
import sqlite3

def RunSiteBot(TOKEN, CHANNEL_ID):
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    # Disable the built-in help command
    bot.remove_command('help')

    @bot.command()
    async def help(ctx):
        embed = discord.Embed(
            title="Bot Commands Help",
            description="List of commands available",
            color=discord.Color.blue()
        )

        embed.add_field(name="!add_website [url] [description]", value="Add a website to the list with its description.", inline=False)
        embed.add_field(name="!update_description [url] [new_description]", value="Update the description of an existing website.", inline=False)
        embed.add_field(name="!list_websites", value="List all stored websites along with their descriptions and reference counts.", inline=False)
        embed.add_field(name="!site_info [url]", value="Displays a breakdown of all the stored data regarding the website.", inline=False)
        embed.add_field(name="!help", value="Displays this help message.", inline=False)

        await ctx.send(embed=embed)

    def current_timestamp():
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    @bot.command()
    async def site_info(ctx, url: str):
        if url.endswith('/'):
            url = url[:-1]

        conn = sqlite3.connect('websites.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM websites WHERE url = ?', (url,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            await ctx.send(f"No information found for URL: {url}")
            return

        # Breakdown of the stored data for the given URL
        response = f"Information for {url}:\n"
        response += f"- Description: {row[2]}\n"
        response += f"- First Referenced: {row[4]}\n"
        response += f"- Last Referenced: {row[5]}\n"
        response += f"- Last Updated: {row[6]}\n"
        response += f"- Updated By: {row[3]}\n"
        response += f"- Total References: {row[7]} times\n"

        await ctx.send(response)


    @bot.command()
    async def update_description(ctx, url: str, *, new_description: str):
        if url.endswith('/'):
            url = url[:-1]
            
        conn = sqlite3.connect('websites.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM websites WHERE url = ?', (url,))
        row = cursor.fetchone()
        if row:
            cursor.execute('UPDATE websites SET description = ?, updated_by = ?, last_updated = ? WHERE url = ?', 
                        (new_description, str(ctx.author), current_timestamp(), url))
            conn.commit()
            await ctx.send(f"Description for {url} has been updated!")
        else:
            await ctx.send(f"No record found for URL: {url}")
        conn.close()

    @bot.command()
    async def add_website(ctx, url: str, *, description = None):
        if description == None:
            await ctx.send("Failed to provide description, please add description to last command.")
            return
        conn = sqlite3.connect('websites.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO websites (url, description, first_referenced, last_referenced) VALUES (?, ?, ?, ?)', 
                        (url, description, current_timestamp(), current_timestamp()))
            conn.commit()
            await ctx.send("Website added successfully!")
        except sqlite3.IntegrityError:
            await ctx.send("This website is already added!")
        finally:
            conn.close()

    @bot.command()
    async def list_websites(ctx):
        conn = sqlite3.connect('websites.db')
        cursor = conn.cursor()
        cursor.execute('SELECT url, description, reference_count FROM websites ORDER BY reference_count DESC')
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            await ctx.send("No websites have been added yet!")
            return

        response = "Websites and Rankings:\n"
        for idx, (url, description, count) in enumerate(rows, start=1):
            response += f"{idx}. {url} - Description: {description} - Referenced: {count} times\n"

        if len(response) > 2000:
            await ctx.send("The list is too long! Displaying the top entries:")
            response = response[:1990] + "..."

        await ctx.send(response)

    @tasks.loop(hours=24)
    async def collect_messages(CHANNEL_ID):
        target_channel_id = CHANNEL_ID  # Replace with your channel's ID
        target_channel = bot.get_channel(target_channel_id)

        if not target_channel:
            print(f"Couldn't find channel with ID {target_channel_id}")
            return

        await target_channel.send("Running Daily Website Reference Collection")

        # Fetch messages from the last 24 hours
        last_24_hours = datetime.utcnow() - timedelta(hours=24)
        messages = []
        async for message in target_channel.history(after=last_24_hours):
            messages.append(message)

        conn = sqlite3.connect('websites.db')
        cursor = conn.cursor()
        
        for message in messages:
            if message.author == bot.user:  # Skip messages from the bot
                continue

            content = message.content
            if content[0] != "!" and ("http://" in content or "https://" in content):
                cursor.execute('SELECT id, description, reference_count FROM websites WHERE url = ?', (content,))
                row = cursor.fetchone()
                if row:
                    new_count = row[2] + 1
                    cursor.execute('UPDATE websites SET reference_count = ? WHERE id = ?', (new_count, row[0]))
                else:
                    default_description = "Scraped from channel - description unknown"
                    current_time = datetime.utcnow()
                    cursor.execute('''
                        INSERT INTO websites 
                        (url, description, reference_count, first_referenced, last_referenced, last_updated, updated_by) 
                        VALUES (?, ?, 1, ?, ?, ?, "BOT")
                    ''', (content, default_description, current_time, current_time, current_time))
                conn.commit()

        cursor.execute('SELECT * FROM websites')
        rows = cursor.fetchall()

        data = []
        for row in rows:
            entry = {
                'id': row[0],
                'url': row[1],
                'description': row[2],
                'first_referenced': row[4],
                'last_referenced': row[5],
                'last_updated': row[6],
                'updated_by': row[3],
                'reference_count': row[7]
            }
            data.append(entry)
        # Saving data to a JSON file
        with open('websites_data.json', 'w') as json_file:
            json.dump(data, json_file, indent=4, default=str)

        conn.close()


    @bot.event
    async def on_ready():
        print(f'Logged in as {bot.user.name} ({bot.user.id})')
        collect_messages.start(CHANNEL_ID)  # This starts the loop

    bot.run(TOKEN)

if __name__ == "__main__":
    with open(".secrets", "r") as f:
        secrets = f.readlines()
    for secret in secrets:
        if secret.startswith("TOKEN"):
            TOKEN = secret.split("=")[1]
        if secret.startswith("CHANNEL_ID"):
            CHANNEL_ID = int(secret.split("=")[1])
    RunSiteBot(TOKEN, CHANNEL_ID)