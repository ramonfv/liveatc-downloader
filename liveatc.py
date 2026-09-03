import re
import time

import requests
from typing import Optional
import urllib.request
from bs4 import BeautifulSoup
import os
import webbrowser


def get_stations(icao):
  page = requests.get(f'https://www.liveatc.net/search/?icao={icao}')
  soup = BeautifulSoup(page.content, 'html.parser')

  stations = soup.find_all('table', class_='body', border='0', padding=lambda x: x != '0')
  freqs = soup.find_all('table', class_='freqTable', colspan='2')

  for table, freqs in zip(stations, freqs):
    title = table.find('strong').text
    up = table.find('font').text == 'UP'
    href = table.find('a', href=lambda x: x and x.startswith('/archive.php')).attrs['href']

    identifier = re.findall(r'/archive.php\?m=([a-zA-Z0-9_]+)', href)[0]

    frequencies = []
    rows = freqs.find_all('tr')[1:]
    for row in rows:
      cols = row.find_all('td')
      freq_title = cols[0].text
      freq_frequency = cols[1].text

      frequencies.append({'title': freq_title, 'frequency': freq_frequency})

    yield {'identifier': identifier, 'title': title, 'frequencies': frequencies, 'up': up}





try:
    import cloudscraper  # type: ignore
except Exception:
    cloudscraper = None

try:
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception:
    sync_playwright = None


def _stream_download(session: requests.Session, url: str, headers: dict, path: str) -> Optional[int]:
    r = session.get(url, headers=headers, stream=True, timeout=60, allow_redirects=True)

    if r.status_code == 404:
        print("⚠️ 404 Not Found (arquivo não existe nesse horário).")
        return r.status_code

    if r.status_code == 403:
        print("❌ 403 (Cloudflare). Parando para evitar bloqueio pior.")
        return r.status_code

    r.raise_for_status()

    # 206 Partial Content é comum por causa do Range
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)

    print(f"✅ Download concluído ({r.status_code}).")
    return r.status_code


def _playwright_download(url: str, headers: dict, path: str) -> Optional[int]:
    if sync_playwright is None:
        print("ℹ️ Playwright não está instalado. Instale para usar o fallback.")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=headers.get("User-Agent"),
                extra_http_headers={
                    "Accept": headers.get("Accept", "*/*"),
                    "Accept-Language": headers.get("Accept-Language", "en-US,en;q=0.9"),
                    "Referer": headers.get("Referer", "https://archive.liveatc.net/"),
                },
            )
            page = context.new_page()

            # Warmup para obter cookies do domínio
            page.goto("https://archive.liveatc.net/", wait_until="domcontentloaded", timeout=60000)

            # Usa o contexto (com cookies) para baixar
            resp = context.request.get(url, timeout=60000)

            if resp.status == 404:
                print("⚠️ 404 Not Found (arquivo não existe nesse horário).")
                browser.close()
                return resp.status

            if resp.status == 403:
                print("❌ 403 (Cloudflare). Parando para evitar bloqueio pior.")
                browser.close()
                return resp.status

            if resp.status >= 400:
                print(f"❌ Erro HTTP {resp.status} no Playwright.")
                browser.close()
                return resp.status

            with open(path, "wb") as f:
                f.write(resp.body())

            browser.close()
            print(f"✅ Download concluído (Playwright {resp.status}).")
            return resp.status
    except Exception as e:
        print(f"❌ Erro no Playwright: {e}")
        return None


def _open_in_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=2)
        print("🌐 Abri a URL no navegador para download manual.")
    except Exception as e:
        print(f"❌ Falha ao abrir navegador: {e}")


def download_archive(remote_folder: str, date: str, time: str, local_folder: str, prefix: str):
    filename = f"{prefix}-{date}-{time}.mp3"
    url = f"https://archive.liveatc.net/{remote_folder}/{filename}"

    local_dir = os.path.join("downloads", local_folder, remote_folder)
    os.makedirs(local_dir, exist_ok=True)
    path = os.path.join(local_dir, filename)

    print(f"🔗 URL: {url}")
    print(f"💾 Salvando em: {path}")

    # Headers bem próximos do Chrome real
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "audio/mpeg,audio/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"https://www.liveatc.net/archive.php?m={remote_folder}",
        "Connection": "keep-alive",
        # Muitos servidores de áudio esperam Range (como browsers fazem)
        "Range": "bytes=0-",
        # Headers "Sec-Fetch" ajudam em alguns WAFs
        "Sec-Fetch-Dest": "audio",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
    }

    with requests.Session() as s:
        try:
            # 1) Warmup: pega cookies no domínio correto
            warm_url = f"https://archive.liveatc.net/"
            r0 = s.get(warm_url, headers=headers, timeout=30, allow_redirects=True)
            # Se aqui já der 403/503, é WAF mais pesado
            if r0.status_code >= 400:
                print(f"⚠️ Warmup retornou {r0.status_code}. Continuando mesmo assim...")

            # 2) Agora baixa do archive com a MESMA sessão (cookies)
            status = _stream_download(s, url, headers, path)

            # 3) Fallback com cloudscraper (se instalado) quando 403
            if status == 403 and cloudscraper is not None:
                print("🔁 Tentando novamente com cloudscraper...")
                scraper = cloudscraper.create_scraper(
                    browser={
                        "browser": "chrome",
                        "platform": "windows",
                        "mobile": False,
                    }
                )
                status = _stream_download(scraper, url, headers, path)

            if status == 403 and cloudscraper is None:
                print("ℹ️ Para tentar bypass do Cloudflare, instale 'cloudscraper'.")

            # 4) Fallback com Playwright quando 403 persistir
            if status == 403:
                print("🔁 Tentando novamente com Playwright...")
                status = _playwright_download(url, headers, path)

            # 5) Último fallback: abrir no navegador para download manual
            if status == 403:
                print("🧭 403 persistente. Abrindo no navegador...")
                _open_in_browser(url)

        except requests.RequestException as e:
            print(f"❌ Erro ao baixar: {e}")


def generate_download_urls(feeds, date, start_time, end_time):
    """Gera lista de URLs para download manual"""
    from main import zulu_range
    
    urls = []
    for feed in feeds:
        try:
            station, prefix, folder = feed.split(',')
        except ValueError:
            print(f"❌ Feed inválido: {feed}")
            continue
            
        for time in zulu_range(start_time, end_time):
            filename = f"{prefix}-{date}-{time}.mp3"
            url = f"https://archive.liveatc.net/{station}/{filename}"
            urls.append(url)
    
    return urls


def download_with_throttle(remote_folder: str, date: str, time: str, local_folder: str, prefix: str, delay: int = 30):
    """Download com delay automático"""
    print(f"⏱️ Aguardando {delay}s antes do download...")
    time.sleep(delay)
    download_archive(remote_folder, date, time, local_folder, prefix)


def interactive_download(feeds, date, start_time, end_time):
    """Download interativo, um por vez com confirmação"""
    from main import zulu_range
    
    for feed in feeds:
        try:
            station, prefix, folder = feed.split(',')
        except ValueError:
            print(f"❌ Feed inválido: {feed}")
            continue
            
        for time in zulu_range(start_time, end_time):
            filename = f"{prefix}-{date}-{time}.mp3"
            url = f"https://archive.liveatc.net/{station}/{filename}"
            
            print(f"\n🔗 Próximo: {url}")
            choice = input("[d]ownload, [o]pen browser, [s]kip, [q]uit: ").lower().strip()
            
            if choice == 'q':
                print("❌ Saindo...")
                return
            elif choice == 's':
                print("⏭️ Pulando...")
                continue
            elif choice == 'o':
                _open_in_browser(url)
                continue
            elif choice == 'd':
                download_archive(station, date, time, folder, prefix)
                # Delay após download bem-sucedido
                time.sleep(20)
            else:
                print("❓ Opção inválida, pulando...")



# download_archive('kpdx_zse', 'Oct-01-2021', '0000Z')
