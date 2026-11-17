# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This repository started as a fork of [xuancong84/OpenHomeKaraoke](https://github.com/xuancong84/OpenHomeKaraoke) (itself based on [vicwomg/pikaraoke](https://github.com/vicwomg/pikaraoke)) and is now maintained on its own. The list below covers everything since the last upstream change it is based on: version 2.5.0, commit `c8c9f7e` (2026-09-11).

## [Unreleased]

### Added

- **New web page**: one React + Material UI app for phones and computers (dark and light, bottom bar on phones, tabs on wide screens) instead of the Bulma/jQuery pages. Home, Queue, Search, Library and Settings; built into `static/app/`, so users need no Node.js. ([fafe83e], [8b571f8])
- **Choice of vocal removal model**: UVR5's VR models HP5 (lead vocal only, default), HP2 and HP3 (all vocals), the baseline model, or L-R/L+R. Weights are downloaded on first use with a checksum check; results are stored per model and playback falls back to the best one there is. ([3ab0232])
- **Apple Silicon GPU (MPS)** for vocal removal, with automatic fallback to the CPU. ([3ab0232])
- **Live download progress** on the phone (percent and elapsed time), and the same link is never downloaded twice at once. ([8b571f8])
- **PO token service (bgutil)**, optional: `python scripts/setup_bgutil.py` installs it, the karaoke starts and stops it by itself (`--no-pot` to leave it off). With it, YouTube refuses fewer downloads and subtitles come through. ([4ab460b])
- **Clear message when YouTube refuses a download as a bot**: a dialog on the phone, in its language, with what to do instead (sing from the library, try later, another network) and, for the admin, the server-side fix. The search page keeps a notice for 30 minutes, and the useless automatic retry is skipped. ([cd49aca])
- **Subtitle languages in order of preference**, kept per phone (default: the page's language, the TV's, English). Only those languages are downloaded, or the video's own language if it has none of them. Older downloads with every language show the TV's language instead of the first track (often Arabic). ([abace76])
- **High quality and subtitles remembered per phone**, shown as switches next to the YouTube search. ([23aa42e])
- Notice on the TV and on every phone when a song is skipped because it cannot be played. ([d24b0b5])
- `nonvocal` / `vocal` folders are created the first time a song folder is used. ([1608450])
- "Background vocal splitting" switch and `--no-vocal`. ([699aa35])
- The web port moves to the next free one when it is taken (AirPlay Receiver holds port 5000 on macOS). ([29badc7])
- Plain-language deployment guides (Python venv, no conda) in English and Taiwan Mandarin, including Steam Deck / Bazzite. ([1608450], [b6ffb9e])
- This changelog.

### Changed

- **The vocal splitter runs as its own process** on every system when PyTorch is installed, instead of multiprocessing or a tmux pane, so PyTorch is no longer loaded into the karaoke itself. It works in segments (memory no longer grows with song length), one per song folder, and stops when the karaoke stops. ([699aa35])
- **macOS: VLC plays inside the karaoke window** (libvlc in-process) instead of its own window, and full screen gets its own Space, so Cmd+Tab and the volume overlay keep working. ([1e95e71], [04b89ab])
- **Browser cookies are off by default and marked experimental** (`-c chrome`, `-c firefox`, `-c auto`, or a `cookies.txt` file), because YouTube may restrict accounts that download a lot. When they are on, the startup log says how many cookies were read and whether YouTube is signed in; Chrome uses the profile that was used last. ([faea257], [6887f9c])
- The WebSocket sends JSON events instead of JavaScript for the page to run; JSON API routes replace the old HTML routes. ([fafe83e])
- yt-dlp gives up after 10 retries with a 15 s timeout instead of retrying forever. ([8b571f8])
- README rewritten for the current setup, options and screenshots ([87e1c43]); the deployment guides no longer send people to the `experimental` and `ui/mui-spa` branches, which are merged, and macOS is now tested.

### Fixed

- **Hangs and freezes around VLC**: the volume check looped forever with newer VLC builds; songs VLC cannot open hung the player; the window stopped responding while VLC started; two VLCs could start at once. Unplayable songs are now skipped. ([c98e21a], [bdbf7a8], [ef68b78], [59209a1])
- Every song was skipped after yt-dlp updated itself (its re-import broke all HTTP requests, including VLC's). ([36b1265])
- macOS: random crash (segmentation fault) shortly after start, caused by a pygame window object freed too early. ([654e7f3])
- HP5, HP2 and HP3 failed with setuptools 81+: librosa pinned to 0.10.2.post1. ([fb9daf8])
- **Security**: song titles and user names could inject script into everyone's page; they are now escaped. ([59209a1])
- Vocal splitter: files that cannot be decoded no longer get the previous song's instrumental; names with quotes work; failing files are recorded and skipped instead of crashing it in a loop; GPU errors fall back to the CPU. ([699aa35])
- Skip and pause no longer fail when nothing is playing; broken placeholders in some machine translations; a phone that reloaded the page stopped getting updates. ([36b1265], [59209a1], [8b571f8])
- Song titles in the library and YouTube results no longer run under the buttons. ([a23b27d])

[fafe83e]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/fafe83e
[8b571f8]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/8b571f8
[3ab0232]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/3ab0232
[4ab460b]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/4ab460b
[cd49aca]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/cd49aca
[abace76]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/abace76
[23aa42e]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/23aa42e
[d24b0b5]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/d24b0b5
[1608450]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/1608450
[699aa35]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/699aa35
[29badc7]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/29badc7
[b6ffb9e]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/b6ffb9e
[1e95e71]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/1e95e71
[04b89ab]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/04b89ab
[faea257]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/faea257
[6887f9c]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/6887f9c
[87e1c43]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/87e1c43
[c98e21a]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/c98e21a
[bdbf7a8]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/bdbf7a8
[ef68b78]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/ef68b78
[59209a1]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/59209a1
[36b1265]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/36b1265
[654e7f3]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/654e7f3
[fb9daf8]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/fb9daf8
[a23b27d]: https://github.com/e-stjernstrom/OpenHomeKaraoke/commit/a23b27d
