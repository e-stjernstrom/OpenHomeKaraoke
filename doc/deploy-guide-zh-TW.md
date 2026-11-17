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

### Steam Deck（SteamOS）、Bazzite 等「不可變」系統（未實測）

這類系統的核心部分是唯讀的：沒有 `sudo apt install`，用系統自己的套件工具做的修改，也可能在下次系統更新時被還原。最簡單的做法是用 **Distrobox**：在你的系統裡跑一個普通的 Ubuntu，和外面共用家目錄、螢幕和聲音。

1. **只有 Steam Deck 要做：** 切到桌面模式（按 Steam 鍵 → 電源 → 切換至桌面），然後打開 **Konsole** 終端機。
2. 確認有 Distrobox：
   ```bash
   distrobox --version
   ```
   Bazzite 和較新的 SteamOS 都有內建。如果找不到這個指令，請照 <https://distrobox.it> 上「不需要 root 的安裝方式」安裝。
3. 建立一個名叫 `karaoke` 的 Ubuntu 24.04 環境。第一次會下載幾百 MB：
   ```bash
   distrobox create --name karaoke --image ubuntu:24.04
   ```
4. 進入這個環境：
   ```bash
   distrobox enter karaoke
   ```
   終端機每一行的開頭會改變，表示你已經在裡面了。在裡面可以用 `sudo apt`（通常不會要求密碼）。
5. 在環境裡面，執行上面 **Linux（Ubuntu）** 的指令，然後照原樣做第 2 到第 5 步。裡外的家目錄是同一個，所以程式一樣會在 `~/OpenHomeKaraoke`，歌曲一樣在 `~/pikaraoke-songs`。
6. **之後每次要用：** 先執行 `distrobox enter karaoke`，再執行[第一次之後，每次要用時](#第一次之後每次要用時)裡的指令。

要注意的事：

- **請用環境裡面的 VLC，不要用應用程式商店裡的 Flatpak 版 VLC。** 卡拉 OK 會直接啟動 `vlc` 程式，並把影片畫進卡拉 OK 視窗；Flatpak 版跑在沙盒裡，這兩件事都會受影響。
- **在 Steam Deck 上，去人聲用的是處理器。** 它的 AMD 顯示晶片不能跑 NVIDIA 的 CUDA，AMD 自己的替代方案（ROCm）也沒有正式支援這顆晶片。請安裝 CPU 版的 PyTorch（第 5a 步），速度會比桌上型電腦慢。
- **用桌面模式最穩。** 從遊戲模式啟動卡拉 OK（例如加成非 Steam 遊戲）還沒有試過。
- **在 Bazzite 上手機連不上？** Bazzite 的防火牆和 Fedora 一樣。請在環境**外面**、一般的終端機裡，執行[手機連不上的話](#手機連不上的話)裡 Fedora 的防火牆指令。

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

**實驗版。** 新功能會先放在一個叫 `experimental` 的分支上試用，目前有：可以選擇去人聲模型（5d），以及在 Apple Silicon Mac 上使用顯示晶片（5e）。要使用實驗版，在上面的 `cd` 之後執行一次：

```bash
git switch experimental
```

要回到一般版本：`git switch master`。

**新網頁（試用）。** 手機上的網頁重新做過了：底部有「首頁／排隊／搜尋／曲庫」四個分頁，可以切換深色和淺色，下載時會顯示進度。它放在 `ui/mui-spa` 分支上（包含實驗版的所有功能），還沒有合併：

```bash
git switch ui/mui-spa
```

這份指南裡的按鈕名稱是照新網頁寫的；`master` 和 `experimental` 還是舊網頁，名稱不同的地方會另外註明。

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
pip install flask==2.3.1 flask-sock pygame==2.5.2 numpy==1.26.4 pydub psutil qrcode pillow pykakasi pinyin unidecode arabic-reshaper python-bidi yt-dlp requests lingua-language-detector
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

- 如果 5000 埠已經被別的程式占用（Mac 上通常是「AirPlay 接收器」），程式會自動改用下一組空的埠，QR code 會顯示新的網址。

1. 手機連上和電腦**同一個 Wi-Fi**。
2. 掃描 QR code，或在手機瀏覽器輸入那個網址。
3. 第一次打開時輸入你的名字（會顯示在你點的歌旁邊）。
4. 到**搜尋**輸入歌名或歌手。曲庫裡已經有的歌會先列出來，點一下就加入排隊。
5. 曲庫裡沒有的話，按**在 YouTube 搜尋**，點一下結果就會下載，下載完自動加入排隊。也可以直接貼上 YouTube 或其他網站（例如 B 站）的連結。

舊網頁（`master`、`experimental`）的做法：在搜尋頁輸入「歌名 karaoke」或「歌名 KTV」，下載後加入待播清單；直接貼連結要打開**進階選項**。

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

### YouTube 要求「確認你不是機器人」

有些網路（公司、學校、共用 Wi-Fi）會被 YouTube 擋下載，或只給低畫質、沒有字幕。

**建議先裝 PO token 服務（bgutil，不用登入任何帳號）。** 它照瀏覽器的方式產生 YouTube 要的「來源證明」（PO token），能減少被擋，字幕也拿得到；但不能保證一定不被擋。需要 git 和 Node.js 22 以上，在程式資料夾執行一次：

```
python scripts/setup_bgutil.py
```

（用虛擬環境的話，請用虛擬環境裡的 python。）之後每次啟動卡拉 OK 都會自動開這個服務，畫面會顯示 `PO token provider: bgutil ... started`。不想用時加 `--no-pot`。

#### 還是被擋：用瀏覽器的登入資料（cookie）

**這是實驗功能，預設關閉。** 用帳號大量下載，YouTube 可能限制那個帳號，請用不重要的小號。

- 在瀏覽器登入 YouTube，啟動時加 `-c chrome` 或 `-c firefox`（`-c auto` 依系統自動選：Mac 上是 Chrome，沒有 Chrome 才用 Firefox 或 Safari）。
- 啟動時畫面會顯示一行 `YouTube sign-in: ...`，`signed in to YouTube: yes` 就表示可以用了。
- **Mac**：要讓啟動卡拉 OK 的程式（例如「終端機」）有「完整磁碟取用權限」：系統設定 → 隱私權與安全性 → 完整磁碟取用權限，打開後把終端機完全結束再重開。第一次下載時 Mac 會問能不能使用「Chrome Safe Storage」，請按「永遠允許」。
- 也可以改用 cookies.txt 檔案（`-c 檔案路徑.txt`）。請在**無痕視窗**登入 YouTube，在 YouTube 頁面匯出，匯出後馬上關掉無痕視窗；用一般視窗匯出的檔案，下載兩三首就會失效。這個檔案等於你的登入資料，不要給別人。

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

**Mac（Apple Silicon M1/M2/M3/M4 和 Intel 都一樣）：** 不要用上面 CPU 那一行，改裝一般版本。在 Apple Silicon 上它還可以用 Mac 的顯示晶片（5e）。

```bash
pip install torch
```

然後，所有人都要執行：

```bash
pip install librosa==0.10.2.post1 soundfile tqdm
```

在測試的電腦上，這兩步加起來不到一分鐘。

### 5b. 它會自己啟動

不用再設定什麼。照平常一樣啟動卡拉 OK（第 4 步）：

```bash
python app.py -w
```

只要裝了 PyTorch，去人聲程式就會跟著卡拉 OK 一起在背景啟動，卡拉 OK 關掉時它也會跟著停。第一次啟動時，程式還會在歌曲資料夾裡建立兩個子資料夾：

- `nonvocal`：去掉人聲的伴奏（唱卡拉 OK 要的就是這個）。
- `vocal`：只有人聲的版本。

它會一次處理一首歌，待播清單裡的歌優先。處理完的歌，手機頁面上就能切換原唱、伴奏、人聲。

注意：它會把**歌曲資料夾裡已經有的每一首歌**都處理一遍。歌很多的話，電腦會忙很久。它只用一半的處理器，而且是低優先順序，所以卡拉 OK 本身還是會很順。

**要花多久？** 在測試的筆電上（8 核心 ARM 處理器，沒有顯示卡，用 4 個核心），一首 40 秒的歌大約花 22 秒，所以 4 分鐘的歌大約要 2 到 3 分鐘。有 NVIDIA 顯示卡會快很多。

### 5c. 關閉和開啟

在手機上打開**設定**（上方的齒輪圖示），**去人聲**卡片裡有一個開關：**人聲分離器**（舊網頁 `master`、`experimental`：**資訊**頁面 → **進階控制選項** → **背景去人聲**）。

- **關閉**：去人聲程式會停下來，不再處理你的歌。已經做好的伴奏和人聲音軌**還是可以播放**。
- **開啟**：從上次停下的地方繼續。

這個設定會記在歌曲資料夾裡（一個名叫 `.vocal_split_disabled` 的小隱藏檔）。如果你設了管理員密碼，只有管理員看得到這個開關。

如果完全不想啟動去人聲程式，啟動卡拉 OK 時加上 `--no-vocal`：

```bash
python app.py -w --no-vocal
```

**處理不了的歌**（下載壞掉的檔案，或其實不是影音的檔案）會被跳過，並記在歌曲資料夾裡一個名叫 `.vocal_failed.json` 的隱藏檔中。除非檔案有變（例如重新下載那首歌），否則不會再試。

**想知道它現在在做什麼？** 它的訊息會寫進記錄檔：Linux 上是 `/dev/shm/vocal_splitter.log`，Windows 和 macOS 上是暫存資料夾裡的 `vocal_splitter.log`。設定裡的**去人聲**卡片也會顯示去人聲程式有沒有在執行；如果它停了，會有**重新啟動**按鈕。

你也還是可以在另一個終端機（啟用 venv 之後）手動執行它，例如想看它工作的過程。同一個資料夾不會同時跑兩個。

```bash
python vocal_splitter.py -d ~/pikaraoke-songs --gpu -1
```

`--gpu -1` 的意思是「用處理器（CPU），不用顯示卡」。如果顯示卡出錯（例如顯示卡太舊，你的 PyTorch 版本不支援），它會自己改用處理器。

### 5d. 選擇模型（只有實驗版）

實驗版和新網頁（第 2 步）可以選模型：新網頁在**設定** → **去人聲** → **模型**；`experimental` 的舊網頁在**資訊**頁面 → **進階控制選項** → **人聲分離器模式**。如果你設了管理員密碼，只有管理員看得到。這個設定對整台卡拉 OK 有效，不是只對某一支手機。

| 選項 | 效果 | 在測試筆電上的速度（CPU，4 核心） |
|---|---|---|
| **HP5**（預設） | 只去除主唱，保留和聲。通常最適合唱卡拉 OK。 | 每 1 分鐘的歌大約要 2 分半 |
| **HP2** | 去除所有人聲，連和聲也去掉。 | 跟 HP5 差不多 |
| **HP3** | 另一個去除所有人聲的版本。如果 HP2 在某首歌留下太多人聲，可以試試看。 | 跟 HP5 差不多 |
| **Baseline** | 程式原本就有的模型。比較輕，大約快 4 倍，但留下的人聲比較多。電腦比較慢的話選它。 | 每 1 分鐘的歌大約 35 秒 |
| **L-R/L+R** | 給 MTV 式卡拉 OK 影片用的老方法。不用 AI，馬上完成，但只對這種影片有效。 | 馬上 |

HP5、HP2、HP3 來自 **Ultimate Vocal Remover（UVR5）**（MIT 授權）。每個模型是一個大約 63 MB 的檔案，不包含在程式下載裡。去人聲程式第一次需要某個模型時，**會自己**從 Hugging Face（`huggingface.co/lj1995/VoiceConversionWebUI`）**下載**，並檢查檔案是否完整。下載的時候，選單上會顯示「下載中……」。檔案會放在程式的 `models/vr` 資料夾；如果程式資料夾不能寫入，就放在 `~/.cache/OpenHomeKaraoke/models/vr`。

如果下載失敗（沒有網路、被防火牆擋住），去人聲程式會先用 **Baseline**，一小時後再試著下載。你也可以自己用瀏覽器從 <https://huggingface.co/lj1995/VoiceConversionWebUI/tree/main/uvr5_weights> 下載檔案，放進 `models/vr`（例如 `models/vr/HP5_only_main_vocal.pth`）。

**已經做好的歌會怎樣？** 每個模型的結果分開保存，不會互相覆蓋：

- Baseline：`nonvocal/<歌名>.m4a`（跟以前一樣）
- HP5、HP2、HP3：`nonvocal/HP5/<歌名>.m4a`，依此類推
- L-R/L+R：`nonvocal/.<歌名>.m4a`（隱藏檔，跟以前一樣）

`vocal` 資料夾也一樣。換成另一個模型之後，去人聲程式會用新模型把歌曲庫再處理一遍，點播清單裡的歌優先。還沒輪到的歌，手機會先播放已經存在的最好結果（依序是 HP5、HP2、HP3、Baseline）。每個模型大約需要跟歌曲音訊差不多大的硬碟空間（128 kbit/s AAC，每條音軌每分鐘大約 1 MB）。

自己手動執行時，可以用 `--model HP2`（或 `HP5`、`HP3`、`baseline`、`LR`）蓋過設定裡的選擇。

### 5e. 顯示卡：NVIDIA 和 Apple Silicon（只有實驗版）

去人聲程式會照下面的順序，挑它找得到的最快的方式：

1. **NVIDIA** 顯示卡（CUDA），如果你的 PyTorch 支援；
2. **Apple Silicon Mac**（M1/M2/M3/M4）的顯示晶片（Apple 稱為「MPS」），用第 5a 步的一般版 PyTorch 就可以；
3. 都沒有的話，就用處理器（CPU）。

記錄檔（5c）的第一行會寫它用的是哪一個，例如 `device mps`。如果顯示晶片記憶體不夠，或有做不到的計算，去人聲程式會自己改用處理器，接著處理同一首歌。少數 Apple 晶片不支援的計算，會自動改在處理器上做。

> **還沒在真正的 Mac 上測試過。** Apple Silicon 這條路只在 Linux 電腦上用模擬的方式測試過（讓程式以為自己有 Apple 晶片）。實際上會不會比 CPU 快、快多少，目前還不知道。如果出問題，可以照常啟動卡拉 OK，但讓去人聲用處理器跑：先 `python app.py -w --no-vocal`，再在第二個終端機執行 `python vocal_splitter.py -d ~/pikaraoke-songs --gpu -1`。

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

刪掉 `OpenHomeKaraoke` 資料夾就好，venv 和裡面的套件會一起刪掉。你的歌曲還留在 `pikaraoke-songs`，要的話也一起刪掉。如果你用了 Distrobox（Steam Deck、Bazzite），再用 `distrobox rm karaoke` 把環境刪掉。

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
那個檔案損壞了，或根本不是影音檔。在**曲庫**裡把它刪掉（歌名旁邊的 ⋮ 按鈕，限管理員；舊網頁在**瀏覽所有歌曲**），再重新下載一次。

**手機頁面打得開，但歌下載不了。**
- 先更新下載工具：`pip install -U yt-dlp`（新網頁也可以在**設定** → **更新下載工具**）。
- 新網頁會顯示下載進度。慢的網站要好幾分鐘；如果網站一直拒絕，大約一分鐘內會顯示「下載失敗」，可以再按一次重試。
- **B 站（bilibili）**：有時候會拒絕下載（終端機裡看到 `HTTP Error 567`），過一陣子再試可能就好。B 站常常這樣，程式這邊沒辦法修。YouTube 連結最可靠。
- 下載完卻只有聲音或只有畫面：沒有裝 ffmpeg，影片和聲音沒辦法合併。照第 1 步裝好 ffmpeg，再下載一次。

**模型選單一直顯示「尚未下載」（實驗版）。**
去人聲程式開始工作時才會下載模型，所以它必須在執行：確認 PyTorch 已經安裝，而且開關是開的（5c）。如果記錄檔說下載失敗，就自己下載檔案（5d）。

**去人聲一直沒有做完。**
確認已經裝好 PyTorch（第 5a 步），而且設定裡的**人聲分離器**開關是開著的（第 5c 步）。接著看第 5c 步提到的記錄檔：裡面會寫它正在處理哪首歌，或為什麼沒有在執行（例如「Python package(s) not installed: torch」）。
