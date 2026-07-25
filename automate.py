import json
import os
import re
import requests
from PIL import Image, ImageDraw, ImageFont

# ১. GitHub Secrets থেকে গোপন লিংকগুলো পড়া
raw_urls = os.getenv("SOURCE_URLS", "")
URLS = [url.strip() for url in raw_urls.split(",") if url.strip()]

# ২. আউটপুট ফোল্ডার তৈরি
OUTPUT_DIR = "output"
IMAGE_DIR = os.path.join(OUTPUT_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)


# ৩. Pillow দিয়ে অটোমেটিক স্পোর্টস কার্ড / ইমেজ জেনারেটর
def generate_sports_image(title, filename):
    width, height = 800, 450
    # ডার্ক ব্যাকগ্রাউন্ড কার্ড
    img = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # নিয়ন বর্ডার (Border)
    draw.rectangle([20, 20, width - 20, height - 20], outline=(132, 204, 22), width=4)

    # ডিফল্ট ফন্ট লোড
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

    # টাইটেল প্রসেসিং
    clean_title = re.sub(r"\s+", " ", title).strip()
    display_title = clean_title if len(clean_title) <= 30 else clean_title[:27] + "..."

    # টেক্সট ড্র করা
    draw.text((400, 80), "LIVE SPORTS", fill=(132, 204, 22), anchor="mm", font=font_small)
    draw.text((400, 225), display_title, fill=(255, 255, 255), anchor="mm", font=font_large)

    image_path = os.path.join(IMAGE_DIR, filename)
    img.save(image_path)
    return image_path


# ৪. M3U পার্স করার ফাংশন
def parse_m3u(content):
    channels = []
    lines = content.splitlines()
    current_item = {}

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            group_match = re.search(r'group-title="([^"]+)"', line)
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)

            category = group_match.group(1) if group_match else "Live TV"
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
        print("❌ কোনো SOURCE_URLS পাওয়া যায়নি! GitHub Secrets চেক করুন।")
        return

    all_data = []
    print("📥 ডাটা ফেচ করা হচ্ছে...")

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
            print(f"❌ Error fetching {url}: {e}")

    # ক্যাটাগরি অনুযায়ী ডাটা সাজানো
    categories = {}
    for item in all_data:
        if not item.get("title") or not item.get("url"):
            continue

        cat = item.get("category", "Live TV").strip().title()
        if cat not in categories:
            categories[cat] = []

        # স্পোর্টসে লোগো না থাকলে Pillow দিয়ে ইমেজ জেনারেট করা
        if cat == "Sports" and not item.get("logo"):
            safe_name = re.sub(r"\W+", "_", item["title"]).lower()[:20]
            img_filename = f"{safe_name}.png"
            item["logo"] = generate_sports_image(item["title"], img_filename)

        categories[cat].append(item)

    print("⚙️ ফাইল তৈরি করা হচ্ছে...")

    master_m3u8 = "#EXTM3U\n"
    master_json = []

    # ক্যাটাগরি ভিত্তিক পৃথক JSON & M3U8 জেনারেট
    for cat, items in categories.items():
        cat_slug = re.sub(r"\W+", "_", cat).lower()

        # ক্যাটাগরি JSON
        json_file = f"category_{cat_slug}.json"
        with open(os.path.join(OUTPUT_DIR, json_file), "w", encoding="utf-8") as f:
            json.dump(items, f, indent=4, ensure_ascii=False)

        # ক্যাটাগরি M3U8
        m3u8_file = f"category_{cat_slug}.m3u8"
        with open(os.path.join(OUTPUT_DIR, m3u8_file), "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in items:
                entry = f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="{cat}",{ch["title"]}\n{ch["url"]}\n'
                f.write(entry)
                master_m3u8 += entry

        master_json.append({
            "category": cat,
            "slug": cat_slug,
            "total_channels": len(items),
            "channels": items
        })

    # অল-ইন-ওয়ান মাস্টার ফাইল তৈরি
    with open(os.path.join(OUTPUT_DIR, "all_channels.json"), "w", encoding="utf-8") as f:
        json.dump(master_json, f, indent=4, ensure_ascii=False)

    with open(os.path.join(OUTPUT_DIR, "all_channels.m3u8"), "w", encoding="utf-8") as f:
        f.write(master_m3u8)

    print("✅ সব ডাটা ও ইমেজ সফলভাবে জেনারেট হয়েছে!")


if __name__ == "__main__":
    main()
