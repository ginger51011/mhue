# mhue - Send Morse code using your Philips Hue[^1] lamps

Dependency free[^2]!

Get help:

```sh
python3 mhue.py --help
```

Usage:

```sh
python3 mhue.py --setup <your Hue bridge IP address>
python3 mhue.py --list
python3 mhue.py --id 1 --text 'hello world' --repeat 5 --wpm 15
```

You could also just use `./mhue.py` and trust in the shebang...

[^1]: I'm in no way associated with Philips Hue, this was based on
[public knowledge of their API](https://www.burgestrand.se/hue-api)_
[^2]: Ok you need a somewhat modern Python
