import json
import asyncio
import aiohttp
from urllib.parse import urlparse
from geoip2.database import Reader

with open('sources.json', 'r') as f:
    sources = json.load(f)['sources']

geo_reader = Reader('GeoLite2-City.mmdb')
EXCLUDED_COUNTRIES = {'UA'}

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

def parse_config(line):
    if line.startswith('trojan://'):
        parsed = urlparse(line)
        params = dict(pair.split('=') for pair in parsed.query.split('&'))
        return {'type': 'trojan', 'server': parsed.hostname, 'port': parsed.port, 'password': parsed.username, 'sni': params.get('sni', parsed.hostname), 'raw': line}
    elif line.startswith('hy2://') or line.startswith('hysteria2://'):
        parsed = urlparse(line)
        params = dict(pair.split('=') for pair in parsed.query.split('&'))
        return {'type': 'hysteria2', 'server': parsed.hostname, 'port': parsed.port, 'password': parsed.username, 'sni': params.get('sni', parsed.hostname), 'raw': line}
    return None

async def check_server(config, session):
    try:
        start = asyncio.get_event_loop().time()
        reader, writer = await asyncio.wait_for(asyncio.open_connection(config['server'], config['port']), timeout=5.0)
        end = asyncio.get_event_loop().time()
        latency = int((end - start) * 1000)
        writer.close()
        await writer.wait_closed()
        
        try:
            response = geo_reader.city(config['server'])
            country_code = response.country.iso_code
        except:
            country_code = 'UNKNOWN'
        
        if country_code in EXCLUDED_COUNTRIES:
            return None
        
        config['latency'] = latency
        config['country_code'] = country_code
        config['name'] = get_server_name(config['server'])
        return config
    except:
        return None

async def main():
    all_configs = []
    async with aiohttp.ClientSession() as session:
        for source_url in sources:
            try:
                async with session.get(source_url, timeout=30) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        for line in text.splitlines():
                            line = line.strip()
                            if not line: continue
                            config = parse_config(line)
                            if config: all_configs.append(config)
            except Exception as e:
                print(f"Ошибка загрузки {source_url}: {e}")
        
        tasks = [check_server(c, session) for c in all_configs]
        results = await asyncio.gather(*tasks)
        
        working = [r for r in results if r is not None and r.get('latency', 9999) <= 500]
        working.sort(key=lambda x: x['latency'])
        final = working[:150]  # Лимит 150 серверов
        
        with open('verified_servers.json', 'w', encoding='utf-8') as f:
            json.dump(final, f, ensure_ascii=False, indent=2)
        
        print(f"Найдено рабочих: {len(working)}. Отобрано: {len(final)}")

if __name__ == '__main__':
    asyncio.run(main())