#!/usr/bin/env python3

"""Python script to blink your Philips Hue lamps with Morse code. Requires requests.

Based on <https://www.burgestrand.se/hue-api> (a bit outdated though).

Philips Hue is a copyright of Signify Holding. That corporation was in no way associated with this script,
or me.

Copyright 2025 Emil Jonathan Eriksson <https://github.com/ginger51011>

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.
If not, see <https://www.gnu.org/licenses/>.
"""

import argparse
import json
import os
import sys
import textwrap
from dataclasses import asdict, dataclass, replace
from time import sleep
from typing import Literal, Self

import requests

S = requests.Session()


def eprint(*args, **kwargs):
    kwargs["file"] = sys.stderr
    print(*args, **kwargs)


@dataclass
class Speed:
    _wpm: int
    _unit_seconds: int
    _dot: int
    _dash: int
    _letter_space: int  # space between letters in a word
    _space: int
    _repeat_pause: int

    def __init__(self, wpm: int):
        # Automagically sets all the other stuff
        self.wpm = wpm

    @property
    def wpm(self) -> int:
        return self._wpm

    @wpm.setter
    def wpm(self, wpm: int) -> None:
        self._wpm = wpm
        self._unit_seconds = 60 / (50 * self._wpm)
        self._dot = self._unit_seconds
        self._dash = 3 * self._dot
        self._letter_space = 3 * self._dot
        self._space = 7 * self._dot
        self._repeat_pause = self._space * 3

    def unit_seconds(self) -> int:
        return self._unit_seconds

    def dot(self) -> int:
        return self._dot

    def dash(self) -> int:
        return self._dash

    def letter_space(self) -> int:
        """Space between letters in a word:"""
        return self._letter_space

    def space(self) -> int:
        return self._space

    def repeat_pause(self) -> int:
        return self._repeat_pause


DEFAULT_SPEED = Speed(15)

# Changing states too quickly breaks lamps
STATE_CHANGE_SECONDS = 1


M = {
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
    # Numbers
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
    "0": "-----",
    # Punctuation (see <https://morsecode.world/international/morse2.html>)
    "&": ".-...",
    "'": ".----.",
    "@": ".--.-.",
    ")": "-.--.-",
    "(": "-.--.",
    ":": "---...",
    ",": "--..--",
    "=": "-...-",
    "!": "-.-.--",  # Not recommended
    ".": ".-.-.-",
    "-": "-....-",
    "+": ".-.-.",
    '"': ".-..-.",
    "?": "..--..",
    "/": "-..-.",
    # Accented
    "À": ".--.-",
    "Æ": ".-.-",
    "Ø": "---.",
    # Swedish
    "Å": ".--.-",
    "Ä": ".-.-",
    "Ö": "---.",
}


def translate(msg: str) -> list[list[list[Literal[".", "-"]]]]:
    """Translates a message to Morse code.

    The result is a list of words, which in turn is a list of characters, which in turn
    is a list of dots and dashes.

    >>> translate('sos')
    [['...', '---', '...']]
    >>> translate('H i?')
    [['....'], ['..', '..--..']]
    """
    msg = msg.upper()
    words = msg.split()
    morse_words = []
    for word in words:
        morse_word = []
        for char in word:
            dots_dashes = M.get(char)
            if dots_dashes is not None:
                morse_word += [dots_dashes]
        morse_words.append(morse_word)
    return morse_words


def clamp(min_x: int, max_x: int, x: int) -> int:
    return max(min(x, max_x), min_x)


@dataclass
class Config:
    ip_address: str
    username: str

    @staticmethod
    def from_json_path(path: str) -> Self | None:
        if not os.path.exists(path):
            eprint(f"ERROR: Did not find config file at {path}")
            return None
        with open(path, encoding="utf-8") as f:
            j = f.read()
            return Config(**json.loads(j))

    def save(self, path: str):
        json_config = json.dumps(asdict(self), indent=4)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_config)

    def base_url(self) -> str:
        """Get the base URL for this username and IP (no trailing `/`)"""
        return f"http://{self.ip_address}/api/{self.username}"

    def list_lamps(self):
        res = S.get(f"{self.base_url()}/lights")
        res.raise_for_status()
        for n, lamp in res.json().items():
            print(f"{n}: {lamp['name']}")


@dataclass
class LampState:
    on: bool
    bri: int
    ct: int

    # These are only available on color lamps
    hue: int | None
    sat: int | None
    xy: list[float] | None

    def __init__(
        self,
        on: bool,
        bri: int,
        ct: int,
        hue: int | None = None,
        sat: int | None = None,
        xy: list[float] | None = None,
        **kwargs,
    ):
        self.on = on

        self.ct = clamp(154, 500, ct)

        # colormode 1
        self.bri = clamp(0, 254, bri) if bri is not None else None
        self.hue = clamp(0, 65535, hue) if hue is not None else None
        self.sat = clamp(0, 254, sat) if sat is not None else None

        # colormode xy
        self.xy = (
            list(map(lambda x: clamp(0, 1, x), xy[:2])) if xy is not None else None
        )


class Lamp:
    def __init__(self, config: Config, id: int):
        self._config = config
        self._id = id
        self._initial_state = None

    def __enter__(self):
        # Ensure we save the lamps initial state to be able to reset it
        self._initial_state = self.current_state()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        # Reset to initial state
        if self._initial_state is not None:
            # OK so a bit messy but: If a Hue light changes color and is turned
            # on in the same command, it will do a nasty flash. But if you don't do
            # it the color wont change...

            # Avoid changing state if we are at desired
            current_state = self.current_state()
            currently_on = current_state.on
            current_state.on = self._initial_state.on

            if current_state != self._initial_state:
                self.set_state(state=self._initial_state)
            elif not currently_on and self._initial_state.on:
                # Should turn on
                self.set_on(True)
            elif currently_on and not self._initial_state.on:
                # Should turn off
                self.set_on(False)

    def initial_state(self) -> LampState | None:
        return self._initial_state

    def current_state(self) -> LampState:
        res = S.get(self.base_url())
        json = res.json()
        contains_hue_error(json, context="get_initial_lamp_state")
        return LampState(**(json.get("state", {})))

    def base_url(self) -> str:
        """Get the base URL for this username and IP (no trailing `/`)"""
        return f"{self._config.base_url()}/lights/{self._id}"

    def set_state(self, state: LampState):
        """Set the current state of the lamp"""
        res = S.put(
            f"{self.base_url()}/state",
            json={**asdict(state), "transitiontime": STATE_CHANGE_SECONDS * 10},
        )
        res.raise_for_status()
        contains_hue_error(res.json(), context="set_lamp")

    def set_on(self, on):
        """Sets a lamp to `on`.

        Use `set_state` to change color and the like
        """
        res = S.put(
            f"{self.base_url()}/state",
            json={"on": on, "transitiontime": 0},
        )
        res.raise_for_status()
        contains_hue_error(res.json(), context="set_lamp")

    def blink(self, duration_s: float):
        self.set_on(on=True)
        sleep(duration_s)
        self.set_on(on=False)

    def blink_morse_word(
        self,
        morse_word: list[list[Literal[".", "-"]]],
        speed: Speed = DEFAULT_SPEED,
    ):
        for i, char in enumerate(morse_word):
            for j, b in enumerate(char):
                if b == ".":
                    self.blink(speed.dot())
                elif b == "-":
                    self.blink(speed.dash())
                # All except last one
                if j < len(morse_word) - 1:
                    sleep(speed.dot())

            # All except last one
            if i < len(morse_word) - 1:
                sleep(speed.letter_space())

    def blink_morse_message(
        self,
        morse_msg: list[list[list[Literal[".", "-"]]]],
        speed: Speed = DEFAULT_SPEED,
    ):
        """Prints a Morse message, divided into words (or special characters)."""
        for i, word in enumerate(morse_msg):
            self.blink_morse_word(word, speed)
            # All except last one
            if i < len(morse_msg) - 1:
                sleep(speed.space())


def contains_hue_error(json: dict, context="unkown") -> bool:
    """Checks JSON for a Hue error, prints it, and returns if an error was found."""
    if isinstance(json, list) and len(json) > 0 and json[0].get("error") is not None:
        eprint(f"ERROR: Bridge responded with {json[0]['error']} (context: {context})")
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
    input("Press the button on your Hue Bridge now; press <Enter> when done")

    res = S.post(
        f"http://{ip}/api",
        json={
            "devicetype": "mhue client",
        },
    )
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
    c = Config(ip_address=ip, username=username)
    c.save(config_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="mhue",
        description=textwrap.dedent(
            """\
            Sends Morse code messages using your Philips Hue lamps.

            The lamp will return to its original state upon completion.

            By Emil Jonathan Eriksson <https://github.com/ginger51011>, licensed under GPL-3.0-or-later.

            Submit a PR at <https://github.com/ginger51011/mhue>!

            WARNING: Do not use if you are sensitive to flashing lights!
            """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=True,
    )
    parser.add_argument(
        "-s",
        "--setup",
        nargs="?",
        type=str,
        metavar="IP",
        help=textwrap.dedent(
            """\
            Setup an application with the provided Hue Bridge IP address
            and saves a configuration (see --output)"
            """
        ),
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
            "-i",
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
    parser.add_argument(
        "-w",
        "--wpm",
        nargs="?",
        type=int,
        metavar="N",
        help="WPM to use. Good range is 10-25, then we're speeding (default: 15)",
        default=15,
    )
    parser.add_argument(
        "-b",
        "--brightness",
        nargs="?",
        type=int,
        metavar="N",
        help="Brightness to use, 0-254",
    )
    parser.add_argument(
        "-H",
        "--hue",
        nargs="?",
        type=int,
        metavar="N",
        help="Hue to use, 0-65535",
    )
    parser.add_argument(
        "-S",
        "--saturation",
        nargs="?",
        type=int,
        metavar="N",
        help="Saturation to use, 0-254",
    )
    parser.add_argument(
        "-x",
        "--xy",
        nargs="*",
        type=float,
        metavar="XY",
        help="Color as array of xy-coordinates (0-1)",
    )
    parser.add_argument(
        "-T",
        "--temperature",
        nargs="?",
        type=int,
        metavar="N",
        help="White color temperature, 154 (cold) - 500 (warm)",
    )

    args = parser.parse_args()

    if args.setup is not None:
        setup(args.setup, args.output)
        sys.exit(0)

    c = Config.from_json_path(args.config_file)
    if c is None:
        sys.exit(1)

    if args.list:
        c.list_lamps()
        sys.exit(0)

    if args.wpm <= 0:
        eprint("WPM must be positive")
        sys.exit(1)
    speed = Speed(args.wpm)

    if args.text is not None and args.id is not None:
        text = translate(args.text)
        with Lamp(config=c, id=args.id) as lamp:
            # We use the initial state of the lamp as default values, but use
            # command line values if passed
            initial_state = lamp.initial_state()
            passed_values = {
                "bri": args.brightness,
                "hue": args.hue,
                "sat": args.saturation,
                "xy": args.xy,
                "ct": args.temperature,
            }
            desired_state = replace(
                initial_state,
                **{k: v for k, v in passed_values.items() if v is not None},
            )

            if desired_state != initial_state:
                # Always turn off; first part of Morse will turn on as well
                desired_state.on = False
                lamp.set_state(desired_state)
                # Give extra time, transition is long
                sleep(STATE_CHANGE_SECONDS * 2)
            else:
                lamp.set_on(False)
                sleep(STATE_CHANGE_SECONDS)

            for _ in range(args.repeat):
                lamp.blink_morse_message(text, speed=speed)
                # All, including last, to return to original state (__exit__) smoothly
                sleep(speed.repeat_pause())
