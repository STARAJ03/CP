import os
import re
import sys
import time
import requests

import core as helper
from vars import API_ID, API_HASH, BOT_TOKEN
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from subprocess import getstatusoutput

bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Dictionary to keep track of users' states and data during /upload flow
user_states = {}


@bot.on_message(filters.command(["start"]))
async def start(bot: Client, m: Message):
    await m.reply_text(
        f"<b>Hello {m.from_user.mention} 👋\n\n"
        "I Am A Bot For Download Links From Your **.TXT** File And Then Upload That File On Telegram.\n"
        "Send /upload to start the upload process.\n"
        "Use /stop to stop any ongoing task.</b>"
    )


@bot.on_message(filters.command("stop"))
async def stop_handler(_, m):
    await m.reply_text("**Stopped**🚦")
    os.execl(sys.executable, sys.executable, *sys.argv)


@bot.on_message(filters.command(["upload"]))
async def upload_start(bot: Client, m: Message):
    user_id = m.from_user.id
    user_states[user_id] = {
        "step": "awaiting_file",
        "chat_id": m.chat.id,
        "links": [],
        "count": 1,
        "batch_name": None,
        "resolution": None,
        "caption": None,
        "thumb": None
    }
    await m.reply_text("𝕤ᴇɴᴅ ᴛxᴛ ғɪʟᴇ ⚡️")


@bot.on_message(filters.document & filters.private)
async def handle_file(bot: Client, m: Message):
    user_id = m.from_user.id
    state = user_states.get(user_id)

    if not state or state.get("step") != "awaiting_file":
        return  # Ignore if user is not in upload flow or not expecting a file

    # Download the file
    file_path = await m.download()
    try:
        with open(file_path, "r") as f:
            content = f.read()
        links = [line.strip() for line in content.splitlines() if line.strip()]
        # Split links on "://", expecting [protocol, rest_of_url]
        links = [link.split("://", 1) for link in links if "://" in link]
        if not links:
            await m.reply_text("**No valid links found in the file.**")
            os.remove(file_path)
            user_states.pop(user_id, None)
            return
        state["links"] = links
        os.remove(file_path)
    except Exception as e:
        await m.reply_text(f"**Invalid file input.**\nError: {e}")
        os.remove(file_path)
        user_states.pop(user_id, None)
        return

    await m.reply_text(f"**𝕋ᴏᴛᴀʟ ʟɪɴᴋ𝕤 ғᴏᴜɴᴅ:** {len(links)}\n\n"
                       "**𝕊ᴇɴᴅ 𝔽ʀᴏᴍ ᴡʜᴇʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ (initial is 1)**")
    state["step"] = "awaiting_start_index"


@bot.on_message(filters.text & filters.private)
async def handle_text(bot: Client, m: Message):
    user_id = m.from_user.id
    state = user_states.get(user_id)
    if not state:
        return

    step = state.get("step")

    if step == "awaiting_start_index":
        # Validate starting index
        try:
            start_index = int(m.text.strip())
            if start_index < 1 or start_index > len(state["links"]):
                await m.reply_text(f"Please enter a number between 1 and {len(state['links'])}")
                return
            state["count"] = start_index
            await m.reply_text("Now Please Send Me Your Batch Name")
            state["step"] = "awaiting_batch_name"
        except ValueError:
            await m.reply_text("Please enter a valid number for start index.")

    elif step == "awaiting_batch_name":
        state["batch_name"] = m.text.strip()
        await m.reply_text(
            "**𝔼ɴᴛᴇʀ ʀᴇ𝕤ᴏʟᴜᴛɪᴏɴ📸**\n"
            "144,240,360,480,720,1080 please choose quality"
        )
        state["step"] = "awaiting_resolution"

    elif step == "awaiting_resolution":
        text = m.text.strip()
        resolutions = {
            "144": "256x144",
            "240": "426x240",
            "360": "640x360",
            "480": "854x480",
            "720": "1280x720",
            "1080": "1920x1080"
        }
        state["resolution"] = resolutions.get(text, "UN")
        await m.reply_text("Now Enter A Caption to add caption on your uploaded file")
        state["step"] = "awaiting_caption"

    elif step == "awaiting_caption":
        highlighter = "️ ⁪⁬⁮⁮⁮"
        if m.text.strip() == 'Robin':
            state["caption"] = highlighter
        else:
            state["caption"] = m.text.strip()
        await m.reply_text(
            "Now send the Thumb url\nEg » https://graph.org/file/ce1723991756e48c35aa1.jpg\n"
            "Or if don't want thumbnail send = no"
        )
        state["step"] = "awaiting_thumb"

    elif step == "awaiting_thumb":
        thumb = m.text.strip()
        if thumb.startswith("http://") or thumb.startswith("https://"):
            # Download thumb
            getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
            state["thumb"] = "thumb.jpg"
        else:
            state["thumb"] = None

        await m.reply_text("Starting the download and upload process... Please wait.")
        state["step"] = "processing"
        await process_links(bot, m, state)
        # After done, cleanup
        user_states.pop(user_id, None)


async def process_links(bot: Client, m: Message, state: dict):
    links = state["links"]
    count = state["count"]
    batch_name = state["batch_name"]
    resolution_code = state["resolution"]
    caption = state["caption"]
    thumb = state["thumb"]

    for i in range(count - 1, len(links)):
        try:
            link_parts = links[i]
            if len(link_parts) < 2:
                continue
            V = link_parts[1].replace("file/d/", "uc?export=download&id=").replace(
                "www.youtube-nocookie.com/embed", "youtu.be"
            ).replace("?modestbranding=1", "").replace("/view?usp=sharing", "")
            url = "https://" + V

            # Classplus and other link adjustments
            if "visionias" in url:
                async with bot.session.get(url) as resp:
                    text = await resp.text()
                    url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)

            elif 'videos.classplusapp' in url:
                url = requests.get(
                    f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url={url}',
                    headers={'x-access-token': 'YOUR_TOKEN_HERE'}
                ).json().get('url', url)

            elif 'tencdn.classplusapp' in url or 'media-cdn' in url or 'webvideos' in url or 'drmcdni' in url:
                url = requests.get(
                    f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url={url}',
                    headers={'x-access-token': 'YOUR_TOKEN_HERE'}
                ).json().get('url', url)

            elif '/master.mpd' in url:
                id_ = url.split("/")[-2]
                url = f"https://d26g5bnklkwsh4.cloudfront.net/{id_}/master.m3u8"

            name1 = link_parts[0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "")\
                .replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
            name = f'{str(i + 1).zfill(3)}) {name1[:60]}'

            if "youtu" in url:
                ytf = f"b[height<={resolution_code}][ext=mp4]/bv[height<={resolution_code}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={resolution_code}]/bv[height<={resolution_code}]+ba/b/bv+ba"

            if "jw-prod" in url:
                cmd = f'yt-dlp -o "{name}.mp4" "{url}"'
            else:
                cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'

            cc = f'**[📽️] Vid_ID:** {str(i + 1).zfill(3)}. {name1}{caption}.mkv\n**𝔹ᴀᴛᴄʜ** » **{batch_name}**'
            cc1 = f'**[📁] Pdf_ID:** {str(i + 1).zfill(3)}. {name1}{caption}.pdf\n**𝔹ᴀᴛᴄʜ** » **{batch_name}**'

            if "drive" in url:
                try:
                    ka = await helper.download(url, name)
                    copy = await bot.send_document(chat_id=m.chat.id, document=ka, caption=cc1)
                    os.remove(ka)
                    time.sleep(1)
                except FloodWait as e:
                    await m.reply_text(str(e))
                    time.sleep(e.x)
                    continue

            elif ".pdf" in url:
                try:
                    pdf_cmd = f'yt-dlp -o "{name}.pdf" "{url}" -R 25 --fragment-retries 25'
                    os.system(pdf_cmd)
                    copy = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)
                    os.remove(f'{name}.pdf')
                except FloodWait as e:
                    await m.reply_text(str(e))
                    time.sleep(e.x)
                    continue

            else:
                Show = (f"**⥥ 🄳🄾🅆🄽🄻🄾🄰🄳🄸🄽🄶⬇️⬇️... »**\n\n"
                        f"**📝Name »** `{name}\n❄Quality » {resolution_code}`\n\n"
                        f"**🔗URL »** `{url}`")
                prog = await m.reply_text(Show)
                res_file = await helper.download_video(url, cmd, name)
                filename = res_file
                await prog.delete(True)
                await helper.send_vid(bot, m, cc, filename, thumb, name, prog)
                time.sleep(1)

        except Exception as e:
            await m.reply_text(f"**Downloading interrupted**\n{str(e)}\n**Name** » {name}\n**Link** » `{url}`")
            continue

    await m.reply_text("**𝔻ᴏɴᴇ 𝔹ᴏ𝕤𝕤😎**")
    if thumb and os.path.exists(thumb):
        os.remove(thumb)


bot.run()
