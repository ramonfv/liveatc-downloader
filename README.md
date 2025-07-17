# LiveATC Downloader

Downloads archived ATC recordings from LiveATC.net.

Currently WIP, may not work correctly for every airport.

Example of use:

Command example to do multiples downloads:

````
python main.py download-multi --icao SBRF --date Jul-10-2025 --start 0000Z --end 0230Z --feeds sbrf_11835,SBRF-Twr,sbrf sbrf_12960,SBRF-App-12960,sbrf sbrf_gnd,SBRF-Gnd,sbrf

````

Some airports have more than one coverage, such as tower, ground, approach/departure, area control center (ACC), and other communications feeds. 

## Communications feeds documentation

For downloads of .mp3 audio files, check the airport availability on liveatc.net: 

````
https://www.liveatc.net/archive.php

````
1. **Ground** 🛫:
- Assignment: Movement manager of aircraft on the ground.
- Flight Stage: Before take off and after landing.


2. **Tower** 🗼:
- Assignment:  Authorizes take-offs and landings, and manages movement on the runways
- Flight Stage: Departure end and arrival start.

3. **Approach/Departure** ✈️:
- Assignment:  Manager departure and approach to the nearest airport.
- Flight Stage: After take-off to cruising level, and from cruising to the start of the final.

4. **ACC – Area Control Center** 🌐:
- Assignment:  Coordinates flights en route/cruise, between approach areas, including those between states or Flight Information Regions (FIRs).
- Flight Stage: During the cruise or long distances.