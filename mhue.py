#!/usr/bin/env python3

"""Dependency-free Python script to blink your Philips Hue lamps with Morse code.

By Emil Jonathan Eriksson <github.com/ginger51011>
"""

import argparse
import json
import os
from dataclasses import dataclass, asdict

import requests as req


@dataclass
class Config:
    ip_address: str
    username: str


# Morse time units
WPM = 20
M_UNIT_SECONDS = 60 / (50 * WPM)  # Approx 20 WPM (five-letter word)
M_DIT = M_UNIT_SECONDS
M_DAHS = 3 * M_DIT
M_LETTER_SPACE = 3 * M_DIT
M_SPACE = 7 * M_DIT


def default_config_path() -> str:
    if (c := os.environ.get("XDG_CONFIG_HOME")) is not None:
        return os.path.join(c, "mhue.json")
    elif (c := os.environ.get("HOME")) is not None:
        return os.path.join(c, ".mhue.json")
    else:
        return ".mhue.json"


def handshake(ip: str) -> str | None:
    res = req.post(
        f"http://{ip}/api",
        json={
            "devicetype": "mhue client",
        },
    )

    input("Press the button on your Hue Bridge now; press any key when done")

    res.raise_for_status()

    json = res.json()

    if len(json) > 0 and json[0].get("error") is not None:
        print(f'ERROR: During handshake, bridge responded with {json[0]["error"]}')
        return None
    elif len(json) > 0:
        return json[0].get("success", {}).get("username", None)
    else:
        return None


def setup(ip: str, config_path: str) -> bool:
    username = handshake(ip)
    if username is None:
        return False
    config = Config(ip_address=ip, username=username)
    json_config = json.dumps(asdict(config), indent=4)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(json_config)


M = {
    "A": ".-",
    # Swedish
    "Å": ".--.-",
    "Ä": ".-.-",
    "Ö": "---.",
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="mhue",
        description="Sends Morse code messages using your Philips Hue lamps",
        add_help=True,
    )
    parser.add_argument(
        "-s",
        "--setup",
        nargs="?",
        type=str,
        metavar="IP",
        help="Setup an application with the provided Hue Bridge IP address and saves a configuration (see --output)",
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=str,
        metavar="PATH",
        help="Where to save the configuration file when used with --setup.",
        default=default_config_path(),
    )
    parser.add_argument(
        "-t",
        "--text",
        nargs="?",
        type=str,
        metavar="TEXT",
        help="Text to display",
    )
    (
        parser.add_argument(
            "-d",
            "--id",
            nargs="?",
            type=int,
            metavar="ID",
            help="Lamp ID to display --text on",
        ),
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List lamp IDs",
    )
    parser.add_argument(
        "-c",
        "--config-file",
        nargs="?",
        type=str,
        metavar="PATH",
        help="Path to config file",
        default=default_config_path(),
    )

    args = parser.parse_args()

    if args.setup is not None:
        setup(args.setup, args.output)
