import json
import geoip2.database

with open('verified_servers.json', 'r', encoding='utf-8') as f:
    servers = json.load(f)

geo_reader = geoip2.database.Reader('GeoLite2-City.mmdb')

country_flags = {'US': '🇺🇸', 'GB': '🇬🇧', 'DE': '🇩🇪', 'FR': '🇫🇷', 'NL': '🇳🇱', 'SE': '🇸🇪', 'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'JP': '🇯🇵', 'KR': '🇰🇷', 'SG': '🇸🇬', 'CA': '🇨🇦', 'AU': '🇦🇺', 'BR': '🇧🇷', 'IN': '🇮🇳', 'IT': '🇮🇹', 'ES': '🇪🇸', 'CH': '🇨🇭', 'AT': '🇦🇹'}
city_names_ru = {'New York': 'Нью-Йорк', 'London': 'Лондон', 'Paris': 'Париж', 'Berlin': 'Берлин', 'Amsterdam': 'Амстердам', 'Tokyo': 'Токио', 'Seoul': 'Сеул', 'Singapore': 'Сингапур'}

def translate_country(country):
    translations = {'United States': 'США', 'United Kingdom': 'Великобритания', 'Germany': 'Германия', 'France': 'Франция', 'Netherlands': 'Нидерланды', 'Sweden': 'Швеция', 'Finland': 'Финляндия', 'Poland': 'Польша', 'Turkey': 'Турция', 'Japan': 'Япония', 'South Korea': 'Южная Корея', 'Singapore': 'Сингапур', 'Canada': 'Канада', 'Australia': 'Австралия', 'Brazil': 'Бразилия', 'India': 'Индия', 'Italy': 'Италия', 'Spain': 'Испания', 'Switzerland': 'Швейцария', 'Austria': 'Австрия'}
    return translations.get(country, country)

def get_server_name(server_ip):
    try:
        response = geo_reader.city(server_ip)
        country = response.country.name
        city = response.city.name
        country_code = response.country.iso_code
    except:
        return 'Неизвестно Неизвестно 🏳️'
    country_ru = translate_country(country)
    city_ru = city_names_ru.get(city, city)
    flag = country_flags.get(country_code, '🏳️')
    return f"{country_ru} {city_ru} {flag}"

def generate_singbox_config(servers):
    outbounds = []
    for srv in servers:
        name = srv.get('name') or get_server_name(srv['server'])
        if srv['type'] == 'trojan':
            outbounds.append({
                "type": "trojan", "tag": name, "server": srv['server'], "server_port": srv['port'],
                "password": srv['password'],
                "tls": {"enabled": True, "server_name": srv['sni'], "utls": {"enabled": True, "fingerprint": "chrome"}}
            })
        elif srv['type'] == 'hysteria2':
            outbounds.append({
                "type": "hysteria2", "tag": name, "server": srv['server'], "server_port": srv['port'],
                "password": srv['password'],
                "tls": {"enabled": True, "server_name": srv['sni'], "insecure": False}
            })
    
    # WARP для защиты от утечек
    outbounds.append({
        "type": "wireguard", "tag": "warp", "server": "engage.cloudflareclient.com", "server_port": 2408,
        "local_address": ["172.16.0.2/32"], "private_key": "YOUR_WARP_PRIVATE_KEY",
        "peer_public_key": "bmV3V2FycF9wdWJsaWNfa2V5", "reserved": [0, 0, 0]
    })
    
    # DNS outbound
    outbounds.append({"type": "dns", "tag": "dns-out"})
    
    # Мосты Tor (опционально)
    outbounds.append({"type": "socks", "tag": "tor", "server": "127.0.0.1", "server_port": 9050, "version": "5"})
    
    config = {
        "log": {"level": "info", "timestamp": True},
        "dns": {
            "servers": [
                {"tag": "dns-remote", "address": "https://1.1.1.1/dns-query", "address_resolver": "dns-local", "detour": "warp"},
                {"tag": "dns-local", "address": "local", "detour": "direct"}
            ],
            "rules": [
                {"domain": ["yandex.ru", "yandex.com", "ya.ru"], "server": "dns-local"},
                {"outbound": "any", "server": "dns-remote"}
            ],
            "final": "dns-remote", "strategy": "prefer_ipv4"
        },
        "inbounds": [{
            "type": "tun", "tag": "tun-in", "interface_name": "utun8", "inet4_address": "172.19.0.1/30",
            "auto_route": True, "strict_route": True, "stack": "system", "sniff": True, "sniff_override_destination": False
        }],
        "outbounds": outbounds,
        "route": {
            "rules": [
                {"protocol": "dns", "outbound": "dns-out"},
                {"geoip": "ru", "outbound": "direct"},
                {"geosite": "category-ads-all", "outbound": "block"}, # Блокировка рекламы
                {"domain": ["youtube.com", "youtu.be", "googlevideo.com"], "outbound": "warp"}, # YouTube
                {"domain": ["t.me", "telegram.org"], "outbound": "warp"}, # Telegram
                {"domain": ["tiktok.com", "tiktokcdn.com"], "outbound": "warp"}, # TikTok
                {"domain": ["whatsapp.com", "whatsapp.net", "wechat.com", "bip.com"], "outbound": "warp"}, # Мессенджеры
                {"domain": ["*.onion"], "outbound": "tor"} # Tor
            ],
            "final": "warp", "auto_detect_interface": True
        },
        "experimental": {"cache_file": {"enabled": True, "path": "cache.db"}}
    }
    return config

config = generate_singbox_config(servers)
with open('subscription.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)
print("Подписка сгенерирована: subscription.json")