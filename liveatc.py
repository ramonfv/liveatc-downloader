import re

import requests
import urllib.request
from bs4 import BeautifulSoup
import os


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


def download_archive(station, date, time, folder, prefix):
    filename = f"{prefix}-{date}-{time}.mp3"
    url = f"https://archive.liveatc.net/{station}/{filename}"
    local_dir = os.path.join("downloads", folder, station)
    os.makedirs(local_dir, exist_ok=True)
    path = os.path.join(local_dir, filename)

    print(f"🔗 URL: {url}")
    print(f"💾 Salvando em: {path}")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
            out_file.write(response.read())
        print("✅ Download concluído.")
    except Exception as e:
        print(f"❌ Erro ao baixar: {e}")



# download_archive('kpdx_zse', 'Oct-01-2021', '0000Z')
