import asyncio
import aiohttp
import re
import base64
import random
from urllib.parse import parse_qs, urlencode
import emoji

# ---------- НАСТРОЙКИ ----------
SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "ready.txt"
MAX_SERVERS = 150
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

# Безопасный парсинг URL с поддержкой IPv6
def parse_proxy_url(url):
    match = re.match(r'^(hy2|trojan)://([^?#]+)(\?.*)?$', url)
    if not match:
        return None, None, None, {}
    protocol = match.group(1)
    host_part = match.group(2)
    query_part = match.group(3) or ""
    
    if host_part.startswith('['):
        bracket_end = host_part.find(']')
        if bracket_end == -1:
            return None, None, None, {}
        host = host_part[1:bracket_end]
        rest = host_part[bracket_end+1:]
        if rest.startswith(':'):
            port = rest[1:]
        else:
            port = None
    else:
        if ':' in host_part:
            host, port = host_part.split(':', 1)
        else:
            host = host_part
            port = None
    
    query_dict = {}
    if query_part:
        query_dict = parse_qs(query_part[1:])
        query_dict = {k: v[0] if v else "" for k, v in query_dict.items()}
    
    return protocol, host, port, query_dict

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

def apply_protection(protocol, host, port, query):
    sni = random.choice(SNI_LIST)
    dns = random.choice(DNS_LIST)
    
    protection = {
        "security": "tls",
        "sni": sni,
        "fp": "chrome",
        "encryption": "none",
        "dns": dns,
    }
    if protocol == "trojan":
        protection["flow"] = "xtls-rprx-vision"
    
    for key, value in protection.items():
        if key not in query or not query[key]:
            query[key] = value
    
    if port:
        if ':' in host:
            host_port = f"[{host}]:{port}"
        else:
            host_port = f"{host}:{port}"
    else:
        if ':' in host:
            host_port = f"[{host}]"
        else:
            host_port = host
    
    query_str = urlencode(query)
    return f"{protocol}://{host_port}?{query_str}"

# ⚠️ ВРЕМЕННО УБРАЛИ ПРОВЕРКУ ПИНГА
async def process_configs(configs):
    valid = []
    tasks = []
    for cfg in configs:
        proto, host, port, query = parse_proxy_url(cfg)
        if not proto or not host:
            continue
        if proto not in ALLOWED_PROTOCOLS:
            continue
        if any(kw in cfg.lower() for kw in EXCLUDED_KEYWORDS):
            continue
        country_name, country_code = parse_location(host)
        if country_code in EXCLUDED_COUNTRIES:
            continue
        tasks.append((cfg, proto, host, port, query, country_name, country_code))
    
    # Проходим по всем без проверки пинга
    for (cfg, proto, host, port, query, country_name, country_code) in tasks:
        protected_cfg = apply_protection(proto, host, port, query)
        name = generate_name(host, country_name, country_code)
        valid.append({"name": name, "url": protected_cfg})
        if len(valid) >= MAX_SERVERS:
            break
    
    valid.sort(key=lambda x: x["name"])
    print(f"✅ Собрано {len(valid)} серверов (без проверки пинга)")
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
    
    # Подсчитаем количество hy2 и trojan
    hy2_count = sum(1 for c in unique if c.startswith("hy2://"))
    trojan_count = sum(1 for c in unique if c.startswith("trojan://"))
    print(f"  - hy2: {hy2_count}, trojan: {trojan_count}")
    
    valid = await process_configs(unique)
    save_subscription(valid)
    print(f"✅ Готово! Результат в {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())