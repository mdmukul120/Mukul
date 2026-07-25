import json
import os
import re
import requests
from PIL import Image, ImageDraw, ImageFont

# ১. GitHub Secrets থেকে লিংক পড়া
raw_urls = os.getenv("SOURCE_URLS", "")
URLS = [url.strip() for url in raw_urls.split(",") if url.strip()]

# ২. আউটপুট নির্দেশিকা সেটআপ
OUTPUT_DIR = "output"
IMAGE_DIR = os.path.join(OUTPUT_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

FONT_FILE = "NotoSansBengali-Bold.ttf"


# ৩. স্পোর্টস কার্ড / ইমেজ জেনারেটর
def generate_sports_image(title, filename):
    size = (800, 450)
    img = Image.new("RGB", size, color=(15, 23, 42))  # Dark Slate BG
    draw = ImageDraw.Draw(img)

    # কার্ডের বর্ডার
    draw.rectangle([20, 20, 780, 430], outline=(132, 204, 22), width=4)

    # ফন্ট লোড
    try:
        if os.path.exists(FONT_FILE):
            font_title = ImageFont.truetype(FONT_FILE, 36)
            font_badge = ImageFont.truetype(FONT_FILE, 22)
        else:
            font_title = font_badge = ImageFont.load_default()
    except Exception:
        font_title = font_badge = ImageFont.load_default()

    # টাইটেল প্রসেস
    clean_title = re.sub(r"\s+", " ", title).strip()
    display_title = (
        clean_title if len(clean_title) <= 35 else clean_title[:32] + "..."
    )

    # ব্যাজ টেক্সট
    draw.text(
        (400, 80),
        "LIVE SPORTS",
        fill=(132, 204, 22),
        anchor="mm",
        font=font_badge,
    )

    # মেইন টাইটেল
    draw.text(
        (400, 225),
        display_title,
        fill=(255, 255, 255),
        anchor="mm",
        font=font_title,
    )

    image_path = os.path.join(IMAGE_DIR, filename)
    img.save(image_path)
    return image_path


# ৪. M3U পার্সার
def parse_m3u(content):
    channels = []
    lines = content.splitlines()
    current_item = {}

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            group_match = re.search(r'group-title="([^"]+)"', line)
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)

            category = group_match.group(1) if group_match else "Uncategorized"
            logo = logo_match.group(1) if logo_match else ""
            title = line.split(",")[-1].strip()

            current_item = {"title": title, "category": category, "logo": logo}
        elif line and not line.startswith("#"):
            if current_item:
                current_item["url"] = line
                channels.append(current_item)
                current_item = {}

    return channels


# ৫. মূল অটোমেশন লজিক
def main():
    if not URLS:
        print("❌ কোনো SOURCE_URLS পাওয়া যায়নি! Secrets টেক্সট চেক করুন।")
        return

    all_data = []
    print("📥 সোর্স লিংক থেকে ডাটা সংগ্রহ করা হচ্ছে...")

    for url in URLS:
        try:
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                if "json" in url.lower() or res.headers.get("Content-Type", "").startswith("application/json"):
                    data = res.json()
                    if isinstance(data, list):
                        for item in data:
                            all_data.append(
                                {
                                    "title": item.get("title", item.get("name", "Sports Event")),
                                    "category": "Sports",
                                    "logo": item.get("logo", item.get("image", "")),
                                    "url": item.get("url", item.get("stream_url", "")),
                                }
                            )
                else:
                    all_data.extend(parse_m3u(res.text))
        except Exception as e:
            print(f"❌ Error loading {url}: {e}")

    # ক্যাটাগরি ফিল্টারিং
    categories = {}
    for item in all_data:
        if not item.get("title") or not item.get("url"):
            continue

        cat = item.get("category", "Uncategorized").strip().title()
        if cat not in categories:
            categories[cat] = []

        # স্পোর্টসে লোগো না থাকলে অটো ইমেজ জেনারেট
        if cat == "Sports" and not item.get("logo"):
            safe_name = re.sub(r"\W+", "_", item["title"]).lower()[:20]
            img_filename = f"{safe_name}.png"
            item["logo"] = generate_sports_image(item["title"], img_filename)

        categories[cat].append(item)

    print("⚙️ ক্যাটাগরি অনুযায়ী ফাইল জেনারেট করা হচ্ছে...")

    master_m3u8 = "#EXTM3U\n"
    master_json_structure = []

    for cat, items in categories.items():
        cat_slug = re.sub(r"\W+", "_", cat).lower()

        # ক্যাটাগরি ভিত্তিক JSON
        with open(os.path.join(OUTPUT_DIR, f"category_{cat_slug}.json"), "w", encoding="utf-8") as f:
            json.dump(items, f, indent=4, ensure_ascii=False)

        # ক্যাটাগরি ভিত্তিক M3U8
        with open(os.path.join(OUTPUT_DIR, f"category_{cat_slug}.m3u8"), "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in items:
                entry = f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="{cat}",{ch["title"]}\n{ch["url"]}\n'
                f.write(entry)
                master_m3u8 += entry

        master_json_structure.append({"category": cat, "slug": cat_slug, "total": len(items), "channels": items})

    # মাস্টার ফাইল সেভ
    with open(os.path.join(OUTPUT_DIR, "all_channels.json"), "w", encoding="utf-8") as f:
        json.dump(master_json_structure, f, indent=4, ensure_ascii=False)

    with open(os.path.join(OUTPUT_DIR, "all_channels.m3u8"), "w", encoding="utf-8") as f:
        f.write(master_m3u8)

    print("✅ প্রসেস সম্পূর্ণ হয়েছে! সব ফাইল output/ ফোল্ডারে সেভ করা হয়েছে।")


if __name__ == "__main__":
    main()
