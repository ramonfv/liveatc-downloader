#!/usr/bin/env python3

from cli import get_args
from liveatc import get_stations, download_archive
from datetime import datetime, timedelta


def zulu_range(start_str, end_str, step_min=30):
  fmt = "%H%MZ"
  start = datetime.strptime(start_str, fmt)
  end = datetime.strptime(end_str, fmt)
  while start <= end:
    yield start.strftime(fmt)
    start += timedelta(minutes=step_min)


def stations(args):
  stations = get_stations(args.icao)
  for station in stations:
    print(f"[{station['identifier']}] - {station['title']}")
    for freq in station['frequencies']:
      print(f"\t{freq['title']} - {freq['frequency']}")
    print()


def download(args):
  date_now = datetime.utcnow()
  last_period = date_now - timedelta(minutes=30) - (date_now - datetime.min) % timedelta(minutes=30)

  date = args.date if args.date else last_period.strftime('%b-%d-%Y')
  time = args.time if args.time else last_period.strftime('%H%MZ')

  download_archive(args.station, date, time, args.folder, args.prefix)


def download_multi(args):
  for feed in args.feeds:
    try:
      station, prefix, folder = feed.split(',')
    except ValueError:
      print(f"❌ Feed inválido: {feed}. Use o formato: station,prefix,folder")
      continue

    for time in zulu_range(args.start, args.end):
      download_archive(station, args.date, time, folder, prefix)


if __name__ == '__main__':
  args = get_args()
  print(args)

  if args.command == 'stations':
    stations(args)
  elif args.command == 'download':
    download(args)
  elif args.command == 'download-multi':
    download_multi(args)
  else:
    print("❌ Comando inválido. Use --help para ver as opções.")
