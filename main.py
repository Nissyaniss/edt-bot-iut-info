import os
from asyncio import sleep
from datetime import datetime

import discord
import fitz
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()


class LatestEdt:

    def __init__(self, filename="", last_modified=datetime(1, 1, 1)):
        self.filename = filename
        self.last_modified = last_modified
        if filename == "":
            self.week_number = 0
        else:
            self.week_number = int(str(filename).split("_")[
                                   1][1:].split(".")[0])


latest_edt_by_class = {
    "A1": LatestEdt(),
    "A2": LatestEdt(),
    "A3": LatestEdt(),
}


def find_file_rows(table):
    """Return every row in the directory listing that points to an actual
    file, skipping folders (href ending in '/'), the 'Parent Directory'
    row, the header row, and any malformed/empty rows."""
    rows = table.find_all("tr")
    file_rows = []

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        link = cols[1].find("a")
        if link is None:
            continue

        href = link.get("href", "")
        if not href or href.endswith("/"):
            continue

        file_rows.append(row)

    return file_rows


async def edt(class_name, ignore_up_to=-1):
    channel = bot.get_channel(int(os.getenv(f"CHANNEL_{class_name}")))
    role = str(os.getenv(f"ROLE_{class_name}"))
    base_url = os.getenv("BASE_URL")

    class_url = f"{base_url}{class_name}"

    try:
        response = requests.get(class_url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[{class_name}] Failed to reach server: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")

    file_rows = find_file_rows(table)
    if not file_rows:
        print(f"[{class_name}] No file row found (only folders or empty listing?).")
        return

    # cols
    # 0 icon
    # 1 name
    # 2 last modified
    # 3 size
    # 4 description
    entries = []
    for row in file_rows:
        cols = row.find_all("td")
        filename = cols[1].find("a").get("href")
        date_str = cols[2].get_text(strip=True)

        try:
            last_modified = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except ValueError:
            last_modified = None

        entries.append(LatestEdt(filename, last_modified))

    entries.sort(key=lambda e: e.week_number)

    current_latest = latest_edt_by_class[class_name]

    for entry in entries:
        if entry.last_modified is None:
            continue

        if entry.week_number <= ignore_up_to:
            continue

        is_new_week = entry.week_number > current_latest.week_number
        is_modification = (
            entry.week_number == current_latest.week_number
            and entry.last_modified > current_latest.last_modified
        )

        if not (is_new_week or is_modification):
            continue

        edt_link = f"{base_url}{class_name}/{entry.filename}?downloadformat=pdf"

        try:
            response = requests.get(edt_link, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[{class_name}] Failed to download PDF for week {entry.week_number}: {e}")
            continue

        with open("edt.pdf", mode="wb") as file:
            file.write(response.content)

        doc = fitz.open("edt.pdf")
        for page in doc:
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            pix.save(f"{class_name}.png")
        doc.close()

        if is_modification:
            await channel.send(
                content=f"<@&{role}> **Modification du [S{entry.week_number}]({edt_link})**",
                file=discord.File(f"./{class_name}.png"),
            )
        else:
            await channel.send(
                content=f"<@&{role}> **[S{entry.week_number}]({edt_link})**",
                file=discord.File(f"./{class_name}.png"),
            )

        os.remove("edt.pdf")
        os.remove(f"{class_name}.png")

        current_latest = entry
        latest_edt_by_class[class_name] = current_latest


bot = discord.Bot()


@bot.slash_command()
@discord.default_permissions(administrator=True)
async def start(ctx, ignore_up_to: int = -1):
    await ctx.respond("Started")

    while True:
        await edt("A1", ignore_up_to)
        await edt("A2", ignore_up_to)
        await edt("A3", ignore_up_to)
        await sleep(60)


bot.run(os.getenv("TOKEN"))
