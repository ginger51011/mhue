#!/usr/bin/env python3

"""Dependency-free Python script to blink your Philips Hue lamps with Morse code.

Based on <https://www.burgestrand.se/hue-api> (a bit outdated though).

By Emil Jonathan Eriksson <github.com/ginger51011>
"""

import argparse
import json
import os
from dataclasses import dataclass, asdict
from typing import Self, Literal
from time import sleep
import sys

import requests as req

# Morse time units
WPM = 20
M_UNIT_SECONDS = 60 / (50 * WPM)  # Approx 20 WPM (five-letter word)
M_DIT = M_UNIT_SECONDS
M_DASH = 3 * M_DIT
M_LETTER_SPACE = 3 * M_DIT
M_SPACE = 7 * M_DIT

M = {
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    # Swedish
    "Å": ".--.-",
    "Ä": ".-.-",
    "Ö": "---.",
}


def translate(msg: str) -> str:
    msg = msg.upper()
    words = msg.split()
    morse_words = []
    for word in words:
        morse_word = ""
        for c in word:
            morse_word += M.get(c, "")
        morse_words.append(morse_word)
    return morse_words


@dataclass
class Controller:
    ip_address: str
    username: str

    @staticmethod
    def from_json_path(path: str) -> Self | None:
        if not os.path.exists(path):
            print(f"ERROR: Did not find config file at {path}")
            return None
        with open(path, encoding="utf-8") as f:
            j = f.read()
            return Controller(**json.loads(j))

    def save(self, path: str):
        json_config = json.dumps(asdict(self), indent=4)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_config)

    def base_url(self) -> str:
        return f"http://{self.ip_address}/api/{self.username}"

    def list_lamps(self):
        res = req.get(f"{self.base_url()}/lights")
        res.raise_for_status()
        for n, lamp in res.json().items():
            print(f'{n}: {lamp["name"]}')

    def set_lamp(self, lamp_id: int, on: bool):
        res = req.put(
            f"{self.base_url()}/lights/{lamp_id}/state",
            json={"on": on, "transitiontime": 2},
        )
        res.raise_for_status()
        contains_hue_error(res.json(), context="set_lamp")

    def blink(self, lamp_id: int, duration_s: float):
        self.set_lamp(lamp_id, on=True)
        sleep(duration_s)
        self.set_lamp(lamp_id, on=False)

    def blink_morse_word(self, lamp_id: int, morse_word: list[Literal[".", "-"]]):
        for i, c in enumerate(morse_word):
            if c == ".":
                self.blink(lamp_id, M_DIT)
            elif c == "-":
                self.blink(lamp_id, M_DASH)
            # All except last one
            if i < len(morse_word) - 1:
                sleep(M_LETTER_SPACE)

    def blink_morse_message(
        self, lamp_id: int, morse_msg: list[list[Literal[".", "-"]]]
    ):
        """Prints a Morse message, divided into words (or special characters)."""
        for i, word in enumerate(morse_msg):
            self.blink_morse_word(lamp_id, word)
            # All except last one
            if i < len(morse_msg) - 1:
                sleep(M_SPACE)


def contains_hue_error(json: dict, context="unkown") -> bool:
    """Checks JSON for a Hue error, prints it, and returns if an error was found."""
    if len(json) > 0 and json[0].get("error") is not None:
        print(f'ERROR: Bridge responded with {json[0]["error"]} (context: {context})')
        return True
    return False


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

    if contains_hue_error(json, context="handshake"):
        return None
    elif len(json) > 0:
        return json[0].get("success", {}).get("username", None)
    else:
        return None


def setup(ip: str, config_path: str) -> bool:
    username = handshake(ip)
    if username is None:
        return False
    c = Controller(ip_address=ip, username=username)
    c.save(config_path)


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
    parser.add_argument(
        "-r",
        "--repeat",
        nargs="?",
        type=int,
        metavar="N",
        help="Repeat message N times",
        default=1,
    )

    args = parser.parse_args()

    if args.setup is not None:
        setup(args.setup, args.output)
        sys.exit(0)

    c = Controller.from_json_path(args.config_file)
    if c is None:
        sys.exit(1)

    if args.list:
        c.list_lamps()
        sys.exit(0)

    if args.text is not None and args.id is not None:
        for i in range(args.repeat):
            c.blink_morse_message(args.id, translate(args.text))
            # All but last time
            if i < args.repeat - 1:
                sleep(M_SPACE * 3)
