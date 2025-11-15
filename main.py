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


a1_latest_edt = LatestEdt()
a2_latest_edt = LatestEdt()
a3_latest_edt = LatestEdt()


async def edt(class_name, ignore_up_to=0):
    channel = ""
    role = ""
    match class_name:
        case "A1":
            global a1_latest_edt
            channel = bot.get_channel(int(os.getenv("CHANNEL_A1")))
            role = str(os.getenv("ROLE_A1"))
        case "A2":
            global a2_latest_edt
            channel = bot.get_channel(int(os.getenv("CHANNEL_A2")))
            role = str(os.getenv("ROLE_A2"))
        case "A3":
            global a3_latest_edt
            channel = bot.get_channel(int(os.getenv("CHANNEL_A3")))
            role = str(os.getenv("ROLE_A3"))

    base_url = os.getenv("BASE_URL")

    class_url = "{base}{className}".format(
        base=base_url,
        className=class_name
    )

    response = requests.get(class_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.find("table")

    rows = table.find_all("tr")
    last_row = rows[len(rows) - 2]  # There is a empty row + len diff

    cols = last_row.find_all("td")
    # cols
    # 0 icon
    # 1 name
    # 2 last modified
    # 3 size
    # 4 description

    filename = cols[1].find("a").get("href")

    date_str = cols[2].get_text(strip=True)

    try:
        last_modified = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        last_modified = None

    latest_edt = LatestEdt(filename, last_modified)

    if (
        (class_name == "A1" and latest_edt.last_modified > a1_latest_edt.last_modified)
        or (class_name == "A2" and latest_edt.last_modified > a2_latest_edt.last_modified)
        or (class_name == "A3" and latest_edt.last_modified > a3_latest_edt.last_modified)
    ) and (ignore_up_to < latest_edt.week_number or ignore_up_to < 0):
        if class_name == "A1":
            a1_latest_edt = latest_edt
        elif class_name == "A2":
            a2_latest_edt = latest_edt
        elif class_name == "A3":
            a3_latest_edt = latest_edt

        edt_link = "{base}{className}/{filename}?downloadformat=pdf".format(
            base=base_url, className=class_name, filename=latest_edt.filename
        )

        response = requests.get(
            "{edt_link}?downloadformat=pdf".format(
                edt_link=edt_link
            )
        )
        response.raise_for_status()

        with open("edt.pdf", mode="wb") as file:
            file.write(response.content)

        doc = fitz.open("edt.pdf")
        for page in doc:
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            pix.save("{className}.png".format(className=class_name))

        doc.close()

        await channel.send(content="<@&{role}> **[S{number}]({link})**".format(number=latest_edt.week_number, role=role, link=edt_link), file=discord.File(
            "./{className}.png".format(className=class_name)))

        os.remove("edt.pdf")
        os.remove("{className}.png".format(className=class_name))


bot = discord.Bot()


@bot.slash_command()
@discord.default_permissions(administrator=True)
async def start(ctx, ignore_up_to: int = -1):
    await ctx.respond("Started")

    while True:
        await edt("A1", ignore_up_to)
        await edt("A2", ignore_up_to)
        await edt("A3", ignore_up_to)
        await sleep(5)


bot.run(os.getenv("TOKEN"))
