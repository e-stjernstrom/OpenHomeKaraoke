# OpenHomeKaraoke: a plain-language setup guide (no conda)

This guide gets OpenHomeKaraoke running on your own computer. You don't need Anaconda or any programming experience. You will copy a few commands into a terminal, one at a time.

> Tested on Linux (Ubuntu-style commands, GNOME desktop, an ARM64 laptop) in November 2026. The Windows and macOS steps follow the same idea but were **not** tested on a real machine.

---

## What you will end up with

- A karaoke screen on your computer (or on the TV it is connected to).
- A QR code on that screen. Anyone on the same Wi-Fi scans it with a phone to search, queue and control songs.
- Optional: **vocal removal**. The program makes an instrumental copy of each song in the background, so you can sing over the music without the original singer.

## What you need

| Thing | Why |
|---|---|
| A computer with Linux, Windows or macOS | It runs the program and shows the karaoke screen |
| About 1 GB of free disk space (about 3 GB with vocal removal) | For the program and its add-ons |
| At least 4 GB of RAM (8 GB or more with vocal removal) | Vocal removal holds the whole song in memory |
| Internet | For setup and for downloading songs |
| A phone on the same Wi-Fi | To pick songs |

You do **not** need an NVIDIA graphics card. Vocal removal also works on the normal processor (CPU), just more slowly.

---

## Words used in this guide

- **Terminal**: a window where you type commands.
  - Linux: press `Ctrl` + `Alt` + `T`, or search the app menu for "Terminal".
  - Windows: open the Start menu and type "PowerShell".
  - macOS: press `Cmd` + `Space`, type "Terminal" and press Enter.
- **Command**: one line of text you paste into the terminal, then press `Enter`.
- **venv** (virtual environment): a private folder holding the Python add-ons this program needs. It keeps them separate from the rest of your computer, so nothing else breaks. If anything goes wrong, you can delete the folder and make it again.

---

## Step 1. Install the basic tools

You need four things: **Python 3.12**, **VLC** (the video player), **ffmpeg** (audio and video conversion) and **git** (to download the program).

> **Why exactly Python 3.12?** Two add-ons the program uses (`pygame` 2.5.2 and `numpy` 1.26.4) don't have ready-made packages for Python 3.13 or newer. Another one (`pydub`) relies on a part of Python that was removed in 3.13. With a newer Python, the install fails or the program won't start.

### Linux (Ubuntu 24.04, Linux Mint 22 and similar)

```bash
sudo apt update
```

```bash
sudo apt install python3.12 python3.12-venv vlc ffmpeg git
```

Your computer will ask for your password. While you type it, nothing appears on screen. That is normal.

On **Fedora**:

```bash
sudo dnf install python3.12 vlc ffmpeg git
```

If your system says there is no `python3.12` package (for example, a very new distribution that only ships 3.13 or newer), see "Python 3.12 is not available" under [When something goes wrong](#when-something-goes-wrong).

Check that it worked:

```bash
python3.12 --version
```

You should see `Python 3.12.something`.

### Windows (untested)

1. Install **Python 3.12** from <https://www.python.org/downloads/> (choose a 3.12.x version, not the newest). On the first screen of the installer, **tick "Add python.exe to PATH"**.
2. Install **VLC** from <https://www.videolan.org/>. Keep the default install location, because the program looks for it there.
3. In PowerShell, install ffmpeg and git:
   ```powershell
   winget install Gyan.FFmpeg
   ```
   ```powershell
   winget install Git.Git
   ```
4. Close PowerShell and open it again, so it picks up the new programs.
5. Check:
   ```powershell
   py -3.12 --version
   ```

> Windows on ARM (for example Snapdragon laptops) has not been tried. Some add-ons may have no ready-made package there.

### macOS (untested)

1. Install Homebrew from <https://brew.sh> if you don't have it.
2. Then:
   ```bash
   brew install python@3.12 ffmpeg git
   ```
   ```bash
   brew install --cask vlc
   ```

### Steam Deck (SteamOS), Bazzite and other "immutable" systems (untested)

On these systems the core of the system is read-only. `sudo apt install` doesn't exist there, and changes made with the system's own package tool may be undone by the next system update. The easiest way around this is **Distrobox**: a normal Ubuntu that runs inside your system and shares your home folder, screen and sound with it.

1. **Steam Deck only:** switch to Desktop Mode (press the Steam button → Power → Switch to Desktop), then open the **Konsole** terminal.
2. Check that Distrobox is there:
   ```bash
   distrobox --version
   ```
   Bazzite and recent SteamOS versions include it. If the command is not found, follow the "install without root" instructions at <https://distrobox.it>.
3. Create an Ubuntu 24.04 box named `karaoke`. This downloads a few hundred MB, once:
   ```bash
   distrobox create --name karaoke --image ubuntu:24.04
   ```
4. Go into the box:
   ```bash
   distrobox enter karaoke
   ```
   The start of the terminal line changes to show you are inside. Inside the box, `sudo apt` works (it usually doesn't ask for a password).
5. Inside the box, do the **Linux (Ubuntu)** commands above, then Steps 2 to 5 exactly as written. Your home folder is the same inside and outside the box, so the program ends up in `~/OpenHomeKaraoke` and the songs in `~/pikaraoke-songs` as usual.
6. **Every time after that:** first run `distrobox enter karaoke`, then the commands under [Every time after the first](#every-time-after-the-first).

Good to know:

- **Use the VLC inside the box, not the Flatpak VLC from the app store.** The karaoke starts the `vlc` program directly and draws its video into the karaoke window. The Flatpak version runs in a sandbox, which gets in the way of both.
- **Vocal removal uses the processor on a Steam Deck.** Its AMD graphics can't run NVIDIA's CUDA, and AMD's own alternative (ROCm) doesn't officially support this chip. Install the CPU version of PyTorch (Step 5a). Expect it to be slower than on a desktop computer.
- **Desktop Mode works best.** Starting the karaoke from Game Mode (for example as a non-Steam game) has not been tried.
- **Phone can't connect on Bazzite?** Bazzite's firewall is the same as Fedora's. Run the Fedora firewall commands from [If the phone can't connect](#if-the-phone-cant-connect) **outside** the box, in a normal terminal.

---

## Step 2. Download the program

Choose where to keep it. These commands put it in your home folder.

```bash
cd ~
```

```bash
git clone https://github.com/e-stjernstrom/OpenHomeKaraoke.git
```

```bash
cd OpenHomeKaraoke
```

This is a fork of the original project. It includes fixes for a freeze where the karaoke window showed "not responding" on Linux desktops, and for songs that fail to play.

**Experimental version.** New features are tried out first on a branch called `experimental`: at the moment, a choice of vocal-removal models (Step 5d) and graphics-card support on Apple Silicon Macs (Step 5e). To use it, run this once after the `cd` above:

```bash
git switch experimental
```

To go back to the normal version: `git switch master`.

**New web page (trial).** The phone page has been rebuilt: four tabs at the bottom (Home, Queue, Search, Library), dark and light themes, and download progress. It is on the `ui/mui-spa` branch (with everything from the experimental version) and not merged yet:

```bash
git switch ui/mui-spa
```

Button names in this guide are those of the new page. `master` and `experimental` still have the old page; where names differ, the old ones are given too.

---

## Step 3. Create the venv and install the add-ons

Make sure you are still inside the `OpenHomeKaraoke` folder (Step 2).

**Linux and macOS:**

```bash
python3.12 -m venv .venv
```

```bash
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -3.12 -m venv .venv
```

```powershell
.venv\Scripts\Activate.ps1
```

If Windows refuses to run the script, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

After activating, the start of the terminal line shows `(.venv)`. **Every command from now on must run with `(.venv)` showing.**

Now install the add-ons (same commands on every system):

```bash
python -m pip install --upgrade pip
```

```bash
pip install flask==2.3.1 flask-sock pygame==2.5.2 numpy==1.26.4 pydub psutil qrcode pillow pykakasi pinyin unidecode arabic-reshaper python-bidi yt-dlp requests lingua-language-detector
```

This took about a minute on the test machine.

> **Why not `pip install -r requirements.txt`?** The project's `requirements.txt` pulls in several gigabytes you don't need: the NVIDIA (CUDA) version of PyTorch and some unrelated packages. The list above is the part the karaoke program itself needs. Vocal removal is a separate, optional step below.

---

## Step 4. Start the karaoke

```bash
python app.py -w
```

- `-w` opens it in a normal window. Leave it out to start in full screen. Press `F` in the karaoke window to switch between window and full screen.
- Songs are saved in a folder called `pikaraoke-songs` in your home folder. The program creates it the first time. To use another folder, add `-d` and the folder, for example `python app.py -w -d ~/Music/karaoke`.
- To choose the display language, add for example `--lang zh_TW` or `--lang en_US`.

The karaoke screen shows a QR code and an address such as `http://192.168.1.23:5000`.

- If port 5000 is already used by another program (on a Mac usually AirPlay Receiver), the program moves to the next free ports by itself, and the QR code shows the new address.

1. Connect your phone to the **same Wi-Fi** as the computer.
2. Scan the QR code, or type the address into the phone's browser.
3. The first time, enter your name (it is shown next to the songs you add).
4. Go to **Search** and type a song or singer. Songs already in your library come first: tap one to add it to the queue.
5. If it isn't in your library, tap **Search YouTube for …**, then tap a result. It downloads and joins the queue by itself. You can also paste a link from YouTube or another site (for example Bilibili).

On the old page (`master`, `experimental`): search for "song name karaoke" on the search page, download it and add it to the queue. To paste a link, open **Advanced**.

To stop the program, go back to the terminal and press `Ctrl` + `C`.

### If the phone can't connect

The computer's firewall may be blocking it.

- **Ubuntu** (only if the firewall is turned on):
  ```bash
  sudo ufw allow 5000/tcp
  ```
- **Fedora**:
  ```bash
  sudo firewall-cmd --add-port=5000/tcp --permanent
  ```
  ```bash
  sudo firewall-cmd --reload
  ```
- **Windows**: when Windows asks whether Python may use the network, allow **private networks**.

---

## Step 5 (optional). Vocal removal

Vocal removal uses an AI model that ships with the program. It needs one more large add-on, **PyTorch**, about 1 GB after install.

### 5a. Install PyTorch and the audio add-ons

With `(.venv)` showing:

**Most computers (no NVIDIA card, or not sure):**

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Computers with an NVIDIA card:** use the selector at <https://pytorch.org/get-started/locally/> (choose Pip, Python and your CUDA version) and run the command it shows.

**Macs (both Apple Silicon M1/M2/M3/M4 and Intel):** use the normal version instead of the CPU line above. On Apple Silicon it can also use the Mac's graphics chip (Step 5e).

```bash
pip install torch
```

Then, for everyone:

```bash
pip install librosa==0.10.2.post1 soundfile tqdm
```

On the test machine these two steps took under a minute together.

### 5b. It starts by itself

Nothing else to set up. Start the karaoke as usual (Step 4):

```bash
python app.py -w
```

When PyTorch is installed, the vocal remover starts in the background together with the karaoke, and stops when the karaoke stops. The first time, the program also creates two sub-folders in your song folder:

- `nonvocal`: the music without the singer (the one you want for karaoke).
- `vocal`: the singer's voice only.

It goes through your songs one at a time, songs in the queue first. When a song is done, the phone page lets you switch between the original, the instrumental and the vocals.

Note: it works through **every song already in the folder**. With a big library this keeps the computer busy for a long time. It uses only half of the processor and runs at low priority, so the karaoke itself stays smooth.

**How long does it take?** On the test laptop (8-core ARM processor, no graphics card, using 4 cores), a 40-second song took about 22 seconds. So a 4-minute song takes roughly 2 to 3 minutes. An NVIDIA card is much faster.

### 5c. Turning it off and on

On the phone, open **Settings** (the gear icon at the top). The **Vocal removal** card has a switch, **Vocal Splitter** (on the old page, `master` and `experimental`: the **Information** page, **Advanced Control Options**, **Background vocal splitting**):

- **Off**: the vocal remover stops and leaves your songs alone. Instrumental and vocal tracks that are already finished **can still be played**.
- **On**: it starts again where it left off.

The setting is remembered in your song folder (a small hidden file called `.vocal_split_disabled`). If you set an admin password, only the admin sees this switch.

To never start the vocal remover at all, start the karaoke with `--no-vocal`:

```bash
python app.py -w --no-vocal
```

**Songs it cannot process** (a damaged download, or a file that isn't really audio or video) are skipped and written down in a hidden file called `.vocal_failed.json` in the song folder. They are not tried again unless the file changes, for example when you download the song again.

**What is it doing right now?** Its messages go to a log file: `/dev/shm/vocal_splitter.log` on Linux, or `vocal_splitter.log` in your temporary folder on Windows and macOS. The **Vocal removal** card in Settings also shows whether the vocal remover is running, with a **Restart** button if it stopped.

You can still run it by hand in a second terminal (with the venv active), for example to watch it work. It won't run twice on the same folder.

```bash
python vocal_splitter.py -d ~/pikaraoke-songs --gpu -1
```

`--gpu -1` means "use the processor (CPU), not a graphics card". If a graphics card fails (for example, a card too old for your PyTorch version), it switches to the processor by itself.

### 5d. Choosing the model (experimental version only)

The experimental version and the new page (Step 2) let you choose the model: on the new page in **Settings** → **Vocal removal** → **Model**, on the old page of `experimental` in the **Information** page → **Advanced Control Options** → **Vocal splitter mode**. Only the admin sees it if you set an admin password. It applies to the whole karaoke, not to one phone.

| Choice | What it does | Speed on the test laptop (CPU, 4 cores) |
|---|---|---|
| **HP5** (default) | Removes only the lead singer and keeps the backing vocals. Usually the nicest for karaoke. | about 2½ minutes of work per minute of song |
| **HP2** | Removes all vocals, backing vocals included. | about the same as HP5 |
| **HP3** | Another version that removes all vocals. Try it if HP2 leaves too much voice in a song. | about the same as HP5 |
| **Baseline** | The model the program always had. Lighter and about 4 times faster, but leaves more of the voice. Choose it on a slow computer. | about 35 seconds per minute of song |
| **L-R/L+R** | The old trick for MTV-style karaoke videos. No AI, instant, and only works on such videos. | instant |

HP5, HP2 and HP3 come from **Ultimate Vocal Remover (UVR5)** (MIT licence). Each one is a file of about 63 MB that is not included in the download. The first time the vocal remover needs one, **it downloads it by itself** from Hugging Face (`huggingface.co/lj1995/VoiceConversionWebUI`) and checks that the file is complete. While it is downloading, the list shows "downloading ...". The files go to the `models/vr` folder of the program, or to `~/.cache/OpenHomeKaraoke/models/vr` if the program folder is read-only.

If the download fails (no internet, a firewall), the vocal remover uses **Baseline** for now and tries the download again an hour later. You can also download the file yourself with a browser from <https://huggingface.co/lj1995/VoiceConversionWebUI/tree/main/uvr5_weights> and put it in `models/vr` (for example `models/vr/HP5_only_main_vocal.pth`).

**What happens to songs that are already done?** Each model keeps its own results, so nothing is overwritten:

- Baseline: `nonvocal/<song>.m4a` (as before)
- HP5, HP2, HP3: `nonvocal/HP5/<song>.m4a` and so on
- L-R/L+R: `nonvocal/.<song>.m4a` (a hidden file, as before)

The same goes for the `vocal` folder. After you switch to another model, the vocal remover goes through your library again with the new model, queued songs first. Until it reaches a song, the phone plays the best result that already exists (HP5, then HP2, HP3, Baseline). Each model needs about as much disk space as the songs' audio again (128 kbit/s AAC, about 1 MB per minute per track).

When running it by hand, `--model HP2` (or `HP5`, `HP3`, `baseline`, `LR`) overrides the choice in Settings.

### 5e. Graphics cards: NVIDIA and Apple Silicon (experimental version only)

The vocal remover picks the fastest thing it finds, in this order:

1. an **NVIDIA** graphics card (CUDA), if your PyTorch supports it;
2. the graphics chip of an **Apple Silicon Mac** (M1/M2/M3/M4; Apple calls this "MPS"), with the normal PyTorch from Step 5a;
3. otherwise the processor (CPU).

The log file (Step 5c) says which one it uses in its first line, for example `device mps`. If the graphics chip runs out of memory or can't do something, the vocal remover switches to the processor by itself and carries on with the same song. A few calculations that Apple's chip doesn't support are done on the processor automatically.

> **Not tested on a real Mac.** The Apple Silicon path was only tested with a simulation on a Linux computer (the program believed it had an Apple chip). Whether it is actually faster than the CPU, and by how much, is not known yet. If it causes problems, start the karaoke as usual and run the vocal remover on the processor: `python app.py -w --no-vocal`, then in a second terminal `python vocal_splitter.py -d ~/pikaraoke-songs --gpu -1`.

---

## Every time after the first

```bash
cd ~/OpenHomeKaraoke
```

```bash
source .venv/bin/activate
```

(Windows: `.venv\Scripts\Activate.ps1`)

```bash
python app.py -w
```

## Updating to a newer version

```bash
cd ~/OpenHomeKaraoke
```

```bash
git pull
```

Then activate the venv and run the `pip install flask==2.3.1 ...` command from Step 3 again.

## Removing everything

Delete the `OpenHomeKaraoke` folder. That also removes the venv and all its add-ons. Your songs stay in `pikaraoke-songs` until you delete that folder too. If you used a Distrobox (Steam Deck, Bazzite), also remove the box with `distrobox rm karaoke`.

---

## When something goes wrong

**`pygame` or `numpy` fails to install, with a long error about "building wheel".**
You are almost certainly not on Python 3.12. Check with `python --version` while `(.venv)` is showing. If it is wrong, delete the `.venv` folder and repeat Step 3 using `python3.12` (Windows: `py -3.12`).

**Python 3.12 is not available on my system.**
Install the small tool `uv` (<https://docs.astral.sh/uv/>). It can download Python 3.12 just for this folder. Then make the venv with `uv venv --seed --python 3.12 .venv` instead of the `python3.12 -m venv .venv` line, and continue Step 3 from `source .venv/bin/activate`.

**"VLC not found" when starting.**
Install VLC (Step 1). If VLC is in an unusual place, tell the program where: `python app.py -w --vlc-path /path/to/vlc`.

**The window says "not responding" or can't be moved (Linux, GNOME/Wayland).**
This happened in the original project and is fixed in this fork. Run `git pull` to make sure you have the latest version.

**A song is skipped with a red "Cannot play" message.**
The file is damaged or isn't a real video or audio file. Delete it in **Library** (the ⋮ button next to the song, admin only; **Browse** on the old page) and download it again.

**The phone page opens but songs won't download.**
- First update the downloader: `pip install -U yt-dlp` (on the new page also **Settings** → **Update download tool**).
- The new page shows download progress. Slow sites can take several minutes. If a site keeps refusing, "Download failed" appears within about a minute, and you can tap again to retry.
- **Bilibili** sometimes refuses downloads (`HTTP Error 567` in the terminal). Trying again later may work. This happens on Bilibili's side and can't be fixed in the program. YouTube links work best.
- Only sound or only picture after a download: ffmpeg is missing, so video and sound could not be joined. Install ffmpeg (Step 1) and download the song again.

**The model list says "not downloaded yet" and it stays that way (experimental version).**
The vocal remover downloads the model when it starts working, so it must be running: check that PyTorch is installed and the switch is on (Step 5c). If the log file says the download failed, download the file yourself (Step 5d).

**Vocal removal never finishes a song.**
Check that PyTorch is installed (Step 5a) and that the **Vocal Splitter** switch in Settings is on (Step 5c). Then look at the log file named in Step 5c: it shows which song it is working on, or why it is not running (for example "Python package(s) not installed: torch").
