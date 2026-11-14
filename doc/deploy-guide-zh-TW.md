# OpenHomeKaraoke 白話安裝指南（不需要 conda）

這份指南帶你在自己的電腦上把 OpenHomeKaraoke 跑起來。不需要 Anaconda，也不需要會寫程式，只要照著把指令一行一行貼進終端機就好。

> 2026 年 11 月在 Linux 上實際測試過（Ubuntu 類的指令、GNOME 桌面、ARM64 筆電）。Windows 和 macOS 的步驟是同樣的做法，但**沒有**在實機上測試過。

---

## 裝好之後會有什麼

- 電腦（或接在電腦上的電視）上會有一個卡拉 OK 畫面。
- 畫面上有一個 QR code。同一個 Wi-Fi 的人用手機掃描，就能搜尋歌曲、點歌、控制播放。
- 選用功能：**去人聲**。程式會在背景替每首歌做一份伴奏版，你就能跟著伴奏唱，聽不到原唱。

## 你需要準備

| 項目 | 用途 |
|---|---|
| 一台 Linux、Windows 或 macOS 電腦 | 執行程式、顯示卡拉 OK 畫面 |
| 約 1 GB 的硬碟空間（要去人聲的話約 3 GB） | 放程式和它需要的套件 |
| 至少 4 GB 記憶體（要去人聲的話建議 8 GB 以上） | 去人聲時會把整首歌放進記憶體 |
| 網路 | 安裝和下載歌曲時要用 |
| 一支連同一個 Wi-Fi 的手機 | 用來點歌 |

**不需要** NVIDIA 顯示卡。去人聲用一般的處理器（CPU）也能跑，只是比較慢。

---

## 本指南用到的名詞

- **終端機**：輸入指令的視窗。
  - Linux：按 `Ctrl` + `Alt` + `T`，或在應用程式選單搜尋「終端機」（Terminal）。
  - Windows：打開「開始」選單，輸入「PowerShell」。
  - macOS：按 `Cmd` + `空白鍵`，輸入「終端機」（Terminal）後按 Enter。
- **指令**：一行文字。貼進終端機後按 `Enter` 執行。
- **venv（虛擬環境）**：一個專門放這個程式所需 Python 套件的資料夾。它和電腦裡的其他東西分開，不會弄壞別的程式。出問題時，把這個資料夾刪掉重建就好。

---

## 第 1 步：安裝基本工具

需要四樣東西：**Python 3.12**、**VLC**（影片播放器）、**ffmpeg**（影音轉檔）、**git**（用來下載程式）。

> **為什麼一定要 Python 3.12？** 程式用到的兩個套件（`pygame` 2.5.2 和 `numpy` 1.26.4）沒有提供給 Python 3.13 以上的現成安裝檔；另一個套件（`pydub`）依賴的 Python 功能在 3.13 被拿掉了。用更新版的 Python，安裝會失敗，或程式啟動不了。

### Linux（Ubuntu 24.04、Linux Mint 22 等）

```bash
sudo apt update
```

```bash
sudo apt install python3.12 python3.12-venv vlc ffmpeg git
```

系統會要求輸入你的密碼。輸入時畫面上不會出現任何字，這是正常的。

**Fedora**：

```bash
sudo dnf install python3.12 vlc ffmpeg git
```

如果系統說找不到 `python3.12` 套件（例如很新的發行版只有 3.13 以上），請看後面[遇到問題時](#遇到問題時)的「系統裝不到 Python 3.12」。

確認有裝好：

```bash
python3.12 --version
```

應該會看到 `Python 3.12.某個數字`。

### Windows（未實測）

1. 從 <https://www.python.org/downloads/> 安裝 **Python 3.12**（請選 3.12.x，不要選最新版）。安裝程式第一個畫面**要勾選「Add python.exe to PATH」**。
2. 從 <https://www.videolan.org/> 安裝 **VLC**。請用預設的安裝位置，程式會到那裡找它。
3. 在 PowerShell 裡安裝 ffmpeg 和 git：
   ```powershell
   winget install Gyan.FFmpeg
   ```
   ```powershell
   winget install Git.Git
   ```
4. 關掉 PowerShell 再重新打開，讓它認得剛裝好的程式。
5. 確認：
   ```powershell
   py -3.12 --version
   ```

> ARM 版 Windows（例如 Snapdragon 筆電）還沒有試過，有些套件可能沒有現成的安裝檔。

### macOS（未實測）

1. 如果還沒有 Homebrew，先到 <https://brew.sh> 安裝。
2. 接著執行：
   ```bash
   brew install python@3.12 ffmpeg git
   ```
   ```bash
   brew install --cask vlc
   ```

---

## 第 2 步：下載程式

先決定要放在哪裡。下面的指令會放在你的家目錄。

```bash
cd ~
```

```bash
git clone https://github.com/e-stjernstrom/OpenHomeKaraoke.git
```

```bash
cd OpenHomeKaraoke
```

這是原專案的分支版本（fork）。它修好了兩個問題：在 Linux 桌面上卡拉 OK 視窗會顯示「沒有回應」而卡住，以及遇到無法播放的歌曲時會卡死。

---

## 第 3 步：建立 venv 並安裝套件

請確認你還在 `OpenHomeKaraoke` 資料夾裡（第 2 步）。

**Linux 和 macOS：**

```bash
python3.12 -m venv .venv
```

```bash
source .venv/bin/activate
```

**Windows（PowerShell）：**

```powershell
py -3.12 -m venv .venv
```

```powershell
.venv\Scripts\Activate.ps1
```

如果 Windows 不讓你執行這個指令碼，先執行下面這行一次，再試一遍：
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

啟用之後，終端機每一行的開頭會出現 `(.venv)`。**接下來所有指令都要在看得到 `(.venv)` 的狀態下執行。**

接著安裝套件（每個系統的指令都一樣）：

```bash
python -m pip install --upgrade pip
```

```bash
pip install flask==2.3.1 flask-sock flask-paginate==2021.10.29 pygame==2.5.2 numpy==1.26.4 pydub psutil qrcode pillow pykakasi pinyin unidecode arabic-reshaper python-bidi yt-dlp requests lingua-language-detector
```

在測試的電腦上大約花了一分鐘。

> **為什麼不用 `pip install -r requirements.txt`？** 專案附的 `requirements.txt` 會多下載好幾 GB 用不到的東西，包括 NVIDIA（CUDA）版的 PyTorch 和一些不相關的套件。上面這份清單只包含卡拉 OK 本身需要的部分。去人聲是另外的選用步驟，在後面。

---

## 第 4 步：啟動卡拉 OK

```bash
python app.py -w
```

- `-w` 表示用一般視窗開啟。不加的話會直接全螢幕。在卡拉 OK 視窗裡按 `F` 可以切換視窗和全螢幕。
- 歌曲會存在家目錄下的 `pikaraoke-songs` 資料夾，第一次啟動時程式會自動建立。想換資料夾就加上 `-d` 和資料夾路徑，例如 `python app.py -w -d ~/Music/karaoke`。
- 想指定畫面語言，可以加上例如 `--lang zh_TW` 或 `--lang en_US`。

卡拉 OK 畫面會顯示 QR code 和一個網址，像是 `http://192.168.1.23:5000`。

1. 手機連上和電腦**同一個 Wi-Fi**。
2. 掃描 QR code，或在手機瀏覽器輸入那個網址。
3. 搜尋歌曲（例如「歌名 karaoke」或「歌名 KTV」），下載後加入待播清單。

要關掉程式，回到終端機按 `Ctrl` + `C`。

### 手機連不上的話

可能是電腦的防火牆擋住了。

- **Ubuntu**（只有在防火牆有開啟時才需要）：
  ```bash
  sudo ufw allow 5000/tcp
  ```
- **Fedora**：
  ```bash
  sudo firewall-cmd --add-port=5000/tcp --permanent
  ```
  ```bash
  sudo firewall-cmd --reload
  ```
- **Windows**：Windows 詢問是否允許 Python 使用網路時，請允許**私人網路**。

---

## 第 5 步（選用）：去人聲

去人聲用的是程式內附的 AI 模型，需要再裝一個比較大的套件 **PyTorch**，裝好後約 1 GB。

### 5a. 安裝 PyTorch 和音訊套件

在看得到 `(.venv)` 的狀態下：

**大多數電腦（沒有 NVIDIA 顯示卡，或不確定有沒有）：**

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**有 NVIDIA 顯示卡的電腦：** 到 <https://pytorch.org/get-started/locally/> 用選單選好（Pip、Python、你的 CUDA 版本），執行它給你的指令。

然後，所有人都要執行：

```bash
pip install librosa==0.10.0 soundfile tqdm
```

在測試的電腦上，這兩步加起來不到一分鐘。

### 5b. 兩個結果資料夾（會自動建立）

第一次啟動卡拉 OK（第 4 步）時，程式會在歌曲資料夾裡建立兩個子資料夾：

- `nonvocal`：去掉人聲的伴奏（唱卡拉 OK 要的就是這個）。
- `vocal`：只有人聲的版本。

你什麼都不用做。去人聲程式會把結果放在這裡；兩個資料夾都在時，手機頁面上的伴奏／人聲切換就會開啟。

注意：資料夾建好之後，去人聲程式會把**歌曲資料夾裡已經有的每一首歌**都處理一遍，一首接一首。歌很多的話，電腦會忙很久。

**想關掉去人聲**，把這兩個資料夾刪掉就好。它們不會再被建立，因為程式在歌曲資料夾裡留了一個名叫 `.vocal_dirs_initialized` 的小隱藏檔，記得已經建立過一次。想再開啟，自己把資料夾建回來（或刪掉那個隱藏檔再重新啟動）。

### 5c. 執行去人聲程式

最簡單的方法：啟動卡拉 OK 時加上 `-V`，它會順便幫你執行去人聲程式。

```bash
python app.py -w -V
```

或者在**另一個**終端機手動執行（先進到資料夾並啟用 venv，做法和第 3 步一樣）：

```bash
python vocal_splitter.py -d ~/pikaraoke-songs --gpu -1
```

`--gpu -1` 的意思是「用處理器（CPU），不用顯示卡」。

它會一首一首處理你的歌。處理完的歌，手機頁面上就能切換原唱、伴奏、人聲。

**要花多久？** 在測試的筆電上（8 核心 ARM 處理器，沒有顯示卡），一首 40 秒的歌大約花 20 秒，所以 4 分鐘的歌大約要 2 分鐘。有 NVIDIA 顯示卡會快很多。它會在背景執行，你可以一邊唱別的歌；但在比較慢的電腦上，播放可能會變得不太順。

> **目前已知的問題**（正在修）：
> - 歌曲資料夾裡如果有損壞的檔案或不是影音的檔案，去人聲程式會當掉、重啟、再當掉，一直循環。
> - 歌名裡有雙引號 `"` 的歌會失敗。
> - 很長的影片（大約一小時）可能會用掉超過 10 GB 記憶體。
>
> 修好之前，歌曲資料夾裡請只放歌，也避免一小時長的影片。

---

## 第一次之後，每次要用時

```bash
cd ~/OpenHomeKaraoke
```

```bash
source .venv/bin/activate
```

（Windows：`.venv\Scripts\Activate.ps1`）

```bash
python app.py -w
```

## 更新到新版本

```bash
cd ~/OpenHomeKaraoke
```

```bash
git pull
```

接著啟用 venv，再執行一次第 3 步的 `pip install flask==2.3.1 ...` 那行指令。

## 全部移除

刪掉 `OpenHomeKaraoke` 資料夾就好，venv 和裡面的套件會一起刪掉。你的歌曲還留在 `pikaraoke-songs`，要的話也一起刪掉。

---

## 遇到問題時

**安裝 `pygame` 或 `numpy` 失敗，出現一長串關於「building wheel」的錯誤。**
幾乎可以確定你用的不是 Python 3.12。在看得到 `(.venv)` 的狀態下用 `python --version` 檢查。如果版本不對，刪掉 `.venv` 資料夾，用 `python3.12`（Windows：`py -3.12`）重做第 3 步。

**系統裝不到 Python 3.12。**
安裝小工具 `uv`（<https://docs.astral.sh/uv/>），它可以只替這個資料夾下載 Python 3.12。把第 3 步的 `python3.12 -m venv .venv` 換成 `uv venv --seed --python 3.12 .venv`，然後從 `source .venv/bin/activate` 繼續做。

**啟動時說找不到 VLC。**
請先安裝 VLC（第 1 步）。如果 VLC 裝在特別的位置，可以告訴程式它在哪裡：`python app.py -w --vlc-path /VLC的/路徑`。

**視窗顯示「沒有回應」或拖不動（Linux，GNOME／Wayland）。**
原專案有這個問題，這個 fork 已經修好了。執行 `git pull` 確認你用的是最新版。

**有首歌被跳過，畫面出現紅色的「無法播放」訊息。**
那個檔案損壞了，或根本不是影音檔。從手機頁面把它刪掉，再重新下載一次。

**手機頁面打得開，但歌下載不了。**
更新 YouTube 下載工具：`pip install -U yt-dlp`。

**去人聲一直沒有做完。**
確認歌曲資料夾裡有 `nonvocal` 資料夾（第 5b 步；如果刪掉了，請自己建回來），而且去人聲程式（第 5c 步）有在執行。那個終端機裡的訊息會顯示它正在處理哪首歌。
