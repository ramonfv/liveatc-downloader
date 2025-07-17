import argparse
import sys

parser = argparse.ArgumentParser()

commands = parser.add_subparsers(title='command', dest='command')

parser_stations = commands.add_parser('stations', help='List stations for a given airport')
parser_stations.add_argument('icao', help='Airport ICAO code, e.g. KPDX')

parser_download = commands.add_parser('download', help='Download MP3 archive for a given station')
parser_download.add_argument('station', help='Station identifier, e.g. kpdx_app')
parser_download.add_argument('-d', '--date', help='Archive date, e.g. Oct-01-2021 defaults to current date (LiveATC only saves archives for 30 days)')
parser_download.add_argument('-t', '--time', help='Archive Zulu time, e.g. 0000Z, defaults to current time')
parser_multi = commands.add_parser("download-multi", help="Baixar várias faixas e feeds")
parser_multi.add_argument("--icao", required=True, help="Código ICAO do aeroporto")
parser_multi.add_argument("--date", required=True, help="Data, ex: Jul-10-2025")
parser_multi.add_argument("--start", required=True, help="Hora inicial, ex: 0000Z")
parser_multi.add_argument("--end", required=True, help="Hora final, ex: 2330Z")
parser_multi.add_argument("--feeds", nargs='+', required=True,
                          help="Lista de feeds no formato station,prefix,folder (ex: sbrf_12960,SBRF-App-12960,sbrf)")



def get_args():
  return parser.parse_args(sys.argv[1:])
