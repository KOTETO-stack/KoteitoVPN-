import asyncio
import aiohttp
import re
import base64
import random
from urllib.parse import urlparse, parse_qs
import emoji

# ---------- НАСТРОЙКИ ----------
SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "ready.txt"
MAX_SERVERS = 150
MAX_PING_MS = 500
EXCLUDED_COUNTRIES = {"UA"}
EXCLUDED_KEYWORDS = ["bns", "bnx"]
ALLOWED_PROTOCOLS = {"hy2", "trojan"}

SNI_LIST = [
    "www.yandex.ru",
    "www.google.com",
    "www.microsoft.com",
    "www.apple.com",
    "www.amazon.com",
    "www.wikipedia.org",
    "www.cloudflare.com",
]

DNS_LIST = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
# ------------------------------

def load_sources():
    with open(SOURCES_FILE, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

async def fetch_configs(session, url):
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                text = await resp.text()
                configs = re.findall(r'(hy2://[^\s]+|trojan://[^\s]+)', text)
                return configs
    except:
        return []
    return []

def parse_location(host):
    country_map = {
        "ru": "Россия", "us": "США", "de": "Германия", "fr": "Франция",
        "nl": "Нидерланды", "sg": "Сингапур", "jp": "Япония", "gb": "Великобритания",
        "ca": "Канада", "au": "Австралия", "it": "Италия", "es": "Испания",
        "br": "Бразилия", "in": "Индия", "kr": "Южная Корея", "tr": "Турция",
        "ae": "ОАЭ", "sa": "Саудовская Аравия", "se": "Швеция", "ch": "Швейцария"
    }
    match = re.search(r'\.([a-z]{2})(?:\.|$)', host)
    if match:
        code = match.group(1).upper()
        if code in country_map:
            return country_map[code], code
    return "Неизвестно", ""

def generate_name(host, country_name, country_code):
    city_match = re.search(r'[.-]([a-z]{3,4})(?:[.-]|$)', host)
    city = city_match.group(1).upper() if city_match else ""
    flag = emoji.emojize(f":{country_code.lower()}:", language='alias') if country_code else "🏳️"
    return f"{country_name} {city} {flag}".strip()

def apply_protection(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    
    sni = random.choice(SNI_LIST)
    dns = random.choice(DNS_LIST)
    
    protection = {
        "security": "tls",
        "sni": sni,
        "fp": "chrome",
        "encryption": "none",
        "dns": dns,
    }
    if url.startswith("trojan://"):
        protection["flow"] = "xtls-rprx-vision"
    
    for key, value in protection.items():
        if key not in query:
            query[key] = [value]
    
    new_query = "&".join([f"{k}={v[0]}" for k, v in query.items()])
    base = url.split("?")[0]
    return f"{base}?{new_query}"

async def tcp_ping(host, port=443, timeout=1.5):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False

async def process_configs(configs):
    valid = []
    tasks = []
    for cfg in configs:
        proto = cfg.split("://")[0]
        if proto not in ALLOWED_PROTOCOLS:
            continue
        if any(kw in cfg.lower() for kw in EXCLUDED_KEYWORDS):
            continue
        parsed = urlparse(cfg)
        host = parsed.hostname or ""
        country_name, country_code = parse_location(host)
        if country_code in EXCLUDED_COUNTRIES:
            continue
        tasks.append((cfg, host, country_name, country_code))
    
    ping_results = await asyncio.gather(
        *[tcp_ping(host) for _, host, _, _ in tasks],
        return_exceptions=True
    )
    
    for (cfg, host, country_name, country_code), alive in zip(tasks, ping_results):
        if alive is True:
            protected_cfg = apply_protection(cfg)
            name = generate_name(host, country_name, country_code)
            valid.append({"name": name, "url": protected_cfg})
            if len(valid) >= MAX_SERVERS:
                break
    
    valid.sort(key=lambda x: x["name"])
    return valid

def save_subscription(valid):
    lines = []
    for item in valid:
        lines.append(f"{item['name']} | {item['url']}")
    content = "\n".join(lines)
    encoded = base64.b64encode(content.encode()).decode()
    with open(OUTPUT_FILE, "w") as f:
        f.write(encoded)

async def main():
    sources = load_sources()
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_configs(session, url) for url in sources]
        results = await asyncio.gather(*tasks)
    
    all_configs = []
    for r in results:
        all_configs.extend(r)
    unique = list(set(all_configs))
    print(f"Найдено {len(unique)} уникальных конфигов")
    
    valid = await process_configs(unique)
    print(f"Отобрано рабочих серверов: {len(valid)}")
    
    save_subscription(valid)
    print(f"✅ Готово! Результат в {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())