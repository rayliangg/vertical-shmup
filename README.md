# Vertical Shmup

縱向彈幕射擊遊戲，附帶一個用 **Stable Baselines3 的 PPO** 訓練的自動駕駛 agent，
會自己閃避敵人和子彈、撿道具、打魔王。有 **pygame 版**，也有免安裝的**網頁版**可以直接拿來 demo。

> 素材都是 2019 年以前的，演算法都是 **2022 年以前**發表的；函式庫的版本說明在下方「2022 年以前檢查」。

![遊戲畫面](docs/screenshots.png)

---

## 目錄

1. [快速開始](#快速開始)
2. [遊戲設計](#遊戲設計)
3. [從訓練到結果的流程](#從訓練到結果的流程)
4. [自動駕駛（PPO）](#自動駕駛ppo)
5. [訓練](#訓練)
6. [訓練時間估計](#訓練時間估計)
7. [網頁版（demo 用）](#網頁版demo-用)
8. [專案結構](#專案結構)
9. [測試](#測試)
10. [2022 年以前檢查](#2022-年以前檢查)

---

## 快速開始

```bash
pip install -e ".[game]"       # 玩遊戲：numpy + pygame
pip install -e ".[game,rl]"    # 再加上 Stable Baselines3（含 PyTorch、gymnasium）：自動駕駛 / 訓練
```

```bash
python -m shmup                 # 自己玩
python -m shmup --autopilot     # 看 PPO 自己玩（要先訓練好模型）
```

**訓練完全不需要畫面**：`core/`（遊戲規則）和 `agent/`（強化學習）都不會 import pygame，
只有自己玩或 demo 的時候才會開視窗。

| 按鍵 | 功能 |
|------|------|
| 方向鍵 / WASD | 移動 |
| Shift | 慢速精準移動（會顯示判定點） |
| X | 炸彈 |
| Tab | 自動駕駛 開 / 關 |
| V | Agent 視角（顯示網路看到的危險格） |
| P / M / Esc | 暫停 / 靜音 / 離開 |

---

## 遊戲設計

參考彈幕射擊遊戲這個類型的經典玩法，全部自己重新實作。

**敵人會開火**：瞄準玩家的「自機狙」、扇形彈、環形彈、旋轉螺旋彈、雷射。

| 敵人 | 行為 |
|------|------|
| Scout | 直直往下飛，發射自機狙 |
| Weaver | 蛇行，發射三向扇形彈 |
| Diver | 停住瞄準一下，然後衝撞玩家 |
| Gunship | 停在畫面上方發射環形彈和雷射，一段時間後離開 |
| 隕石 | 大的打碎會分裂成兩個中的，中的再分裂成小的 |

**道具**：火力升級（最多 4 級）、回血、護盾（擋一次攻擊）、炸彈、加分星星。

**彈幕遊戲的經典機制**：

- 判定點只有 5 px，子彈從身邊擦過（擦彈）會加分
- 炸彈會清掉全畫面子彈；被打中時如果還有炸彈，會**自動放炸彈**抵銷
- 被打之後有一段無敵時間，火力會降一級
- 飛到畫面上方的「收點線」，所有道具會自動吸過來

### 魔王關卡

遊戲一共 **2 關**，每一關都是「雜魚波次（約 60 秒）→ WARNING → 魔王」。
第 1 關一隻魔王，**第 2 關（最後一關）是兩隻魔王同時出場**，兩關打完就結束：

```
第 1 關：雜魚 → WARDEN（1 隻）
第 2 關：雜魚 → TWIN FANG（2 隻，一左一右）→ ALL CLEAR
```

| 關卡 | 魔王 | 第 1 階段 | 第 2 階段 | 第 3 階段 |
|------|------|-----------|-----------|-----------|
| 1 | WARDEN | Aimed Fans：五向自機狙 + 慢速大彈環 | Twin Spiral：雙螺旋 + 雷射 | Last Stand：密集環形彈 + 高速自機狙 |
| 2（最後一關） | TWIN FANG x2 | Crossfire：雙砲口交叉雷射 | Pinwheel：反向旋轉的風車彈 | Fang Rush：兩隻一左一右夾擊玩家 |

- 每隻魔王 HP 剩 66%、33% 時換階段，畫面上的子彈會被清掉，並顯示階段名稱
- 每個階段有 30 秒時限：時間內打破有 +1000 分；時間到直接換下一階段；最後階段時間到魔王會逃走
- 第 2 關的兩隻 TWIN FANG 各自有血條和階段；**先打倒一隻，另一隻會暴走（RAGE），射速變兩倍**
- 兩隻都打倒就 **ALL CLEAR**，加 20,000 分 + 每剩 1 滴血 5,000 分，遊戲結束

### 畫面風格

參考縱向彈幕射擊遊戲常見的版面（這個類型的共同慣例，不是照抄某一款遊戲）：

- **右邊資訊面板**：遊戲區在左邊，右邊是有外框的面板，顯示 HI-SCORE、SCORE、PLAYER（剩幾條命）、
  BOMB、POWER、GRAZE、STAGE；自動駕駛時還會顯示 3x3 搖桿燈號，看 AI 選了哪個方向、有沒有開慢速
- **魔王血條在上方**：每隻魔王一條，有階段刻度、魔王名稱和階段倒數秒數；雙魔王時會有兩條
- **ENEMY 標記**：遊戲區最下面有紅色三角形，標出魔王現在的左右位置
- **關卡標題帶**：STAGE、WARNING、ALL CLEAR 會用橫跨整個遊戲區的色帶顯示

![魔王](docs/bosses.png)

---

## 從訓練到結果的流程

```
[1] 遊戲規則  src/shmup/core/
     │   純 Python 模擬，不用畫面，同一個 seed 一定跑出同一局
     ▼
[2] gymnasium 環境  src/shmup/agent/env.py、features.py
     │   每 2 個 frame 做一次決策（每秒 30 次）
     │   觀測：284 個數字（自機、最近 24 顆子彈、最近 8 個敵人、9x9 危險格、道具、魔王）
     │   動作：18 種（9 個方向 x 一般 / 慢速）
     │   獎勵：活著 +0.01、掉血 -1、吃道具 +0.05、ALL CLEAR +5 …
     ▼
[3] 訓練  scripts/train_cpu.py（本機）或 scripts/train_gpu.py（Colab），Stable Baselines3 PPO
     │   ┌─▶ SubprocVecEnv：同時玩 8 局，每局一個程序，用滿所有 CPU 核心
     │   │     ▼
     │   │   每局走 1,024 步 → 一批 8,192 筆資料（依策略的機率抽樣動作 = 探索）
     │   │     ▼
     │   │   用 GAE 算每一步的 advantage（這個動作比平常好多少）
     │   │     ▼
     │   │   PPO 剪裁目標，同一批資料學 10 輪 → 丟掉，重新收集
     │   └─────┘
     ▼   每 20 萬步 / 第 10、50、500、2000 回合
[4] 評估與存檔  固定 seed、選機率最高的動作玩 5 局
     │   ├─▶ 存活最久的模型    → models/ppo/best_model.zip
     │   ├─▶ 最新模型          → models/ppo/last_model.zip（斷線時用 --resume 接著訓練）
     │   └─▶ 里程碑            → models/ppo/checkpoints/ppo_ep{10,50,500,2000}.zip
     ▼   玩滿 2000 回合自動停止
[5] 匯出  scripts/export_web.py
     │   best_model.zip 的策略網路 → web/model/ppo_model.js（權重轉成 base64）
     ▼
[6] 看結果（這一步才需要畫面）
     ├─▶ pygame 版：python -m shmup --autopilot
     ├─▶ 網頁版：  web/index.html（純 JavaScript 推論，可以開危險格、直接打魔王）
     └─▶ 錄影：    scripts/record_video.py（第 10 / 50 / 500 / 2000 回合的模型各錄一支，同一個 seed）
```

---

## 自動駕駛（PPO）

用 [Stable Baselines3](https://github.com/DLR-RM/stable-baselines3) 的 **PPO**。選它的原因：

- **動作是 18 種離散選擇**：PPO 輸出每個動作的機率，剛好適合（SAC、TD3 是給連續動作的，不適用）。
- **遊戲模擬可以平行跑**：8 個程序同時玩，本機實測每秒約 3,700–4,000 步（上一版自己寫的 DQN 約 900 步）。
  PPO 「需要大量資料」的缺點在這裡不是問題。
- **穩定、幾乎不用調參**：PPO 的剪裁讓每次更新只走一小步，訓練很少崩掉。
- **推論簡單**：demo 時只跑策略網路、選機率最高的動作，網頁版用純 JavaScript 就能算。
- SB3 官方也建議 PPO + MLP 用 CPU 跑，Mac 沒有 CUDA 也沒關係。

| 方法 | 出處 | 用途 |
|------|------|------|
| PPO（剪裁目標） | Schulman et al., 2017 | 主要演算法 |
| GAE（λ = 0.95） | Schulman et al., 2015 | 算 advantage |
| Actor-Critic | Mnih et al., 2016（A3C / A2C） | 策略網路 + 價值網路 |
| Adam、熵獎勵、梯度裁剪 | 2014 年以前 / PPO 論文 | 優化與探索 |

- **觀測（284 維）**：不是看畫面像素，而是整理好的數字，所以小的 MLP 就學得動，瀏覽器也跑得動。
- **動作（18 種）**：9 個方向 x {一般速度, 慢速}。射擊一直是自動的，agent 只負責移動。
- **獎勵**：每步存活 +0.01、掉 1 滴血 -1、被迫自動放炸彈 -0.5、護盾破掉 -0.3、
  撿道具 +0.05、分數 x 0.0002、死亡 -1、ALL CLEAR +5。
- **網路**：策略網路和價值網路各兩層 x 256 單元（tanh），共 282,387 個參數；GPU 版每層 512。

詳細的原理和設計理由寫在 `README2.md`（個人筆記，沒有放進 git）。

---

## 訓練

```bash
python scripts/train_cpu.py                       # 用全部 CPU 核心玩到 2000 回合
python scripts/train_cpu.py --max-episodes 300    # 快速試跑
python scripts/train_cpu.py --resume models/ppo/last_model.zip       # 接著上次訓練
python scripts/train_cpu.py --eval-only models/ppo/best_model.zip    # 只評估
python scripts/train_cpu.py --help                # 所有超參數都能用參數調整
python scripts/train_gpu.py                       # NVIDIA GPU（CUDA），例如 Colab
```

預設就會：

- **用滿所有 CPU 核心**：同時玩「核心數」局，每局一個程序（`--n-envs` 可以改）
- **玩滿 2000 回合就停**（`--max-episodes`）
- **在第 10 / 50 / 500 / 2000 回合各存一份模型**到 `models/ppo/checkpoints/ppo_ep{N}.zip`，順便評估 5 局（`--save-episodes`）
- 每 20 萬步評估一次，存活最久的存成 `models/ppo/best_model.zip`
- 最新的模型存成 `models/ppo/last_model.zip`，回合數記在 `last_progress.json`；按 Ctrl+C 中斷也會存

**同一時間只跑一個訓練**：兩個訓練會搶同一批核心，也會寫到同一個 `models/ppo/` 資料夾。

### 錄影：比較不同訓練程度的 agent

```bash
python scripts/record_video.py                       # 錄第 10 / 50 / 500 / 2000 回合的模型
python scripts/record_video.py --episodes 50 2000 --seconds 60
```

每個模型都用同一個 seed 玩一局，畫面跟 pygame 版一樣（含右邊面板和 AI 搖桿燈號），
輸出到 `videos/episode_0010.mp4` 等，另外合成一支 2x2 對照影片 `videos/compare_2x2.mp4`。
不用開視窗；需要電腦裡有 ffmpeg。

### 在 Google Colab 上訓練

1. 在本機打包程式碼，把 zip 上傳到 Google Drive 根目錄：

   ```bash
   cd ~/Desktop && zip -qr vertical-shmup.zip vertical-shmup -x "vertical-shmup/.git/*" "vertical-shmup/models/*" "vertical-shmup/videos/*" "*/__pycache__/*" "vertical-shmup/README2.md" "*.DS_Store"
   ```

2. 到 Colab 上傳 `notebooks/train_on_colab.ipynb`，**執行階段 → 變更執行階段類型 → T4 GPU**，依序執行每個 cell
   （會先 `pip install stable-baselines3`）。
3. 模型、log、影片都會寫到 `MyDrive/shmup/`，斷線後用 `--resume` 接著訓練。
4. 下載 `best_model.zip` 放到 `models/ppo/`，`ppo_model.js` 放到 `web/model/`，回到本機 demo。

Colab 免費版只有 2 個 CPU 核心，同時只能跑 2 局；這個專案的瓶頸是遊戲模擬，所以 **8 核的 Mac 通常比 Colab 快**。

---

## 訓練時間估計

「訓練 N 回合」指 N 個 episode（一局遊戲，從開始到死亡、ALL CLEAR，或滿 15,000 步約 8 分鐘）。
一開始 agent 幾乎是亂動，一局大約 1,000 步；學會閃避之後一局會越來越長。

| 訓練回合數 | 約等於幾步決策 | 這時候的 agent | CPU 版（本機 Mac 8 核） | GPU 版（Colab T4，估計） |
|-----------:|---------------|----------------|------------------------:|-------------------------:|
| 10 | 約 1 萬步 | 幾乎是亂動 | 約 10 秒 | 約 20 秒 |
| 50 | 約 6 萬步 | 剛開始學 | 約 30 秒 | 約 1–2 分鐘 |
| 200 | 約 25 萬步 | 開始會閃一些子彈 | 約 1–2 分鐘 | 約 3–5 分鐘 |
| 2000 | 約 300–500 萬步 | 預期能撐到魔王戰（實際要看訓練結果） | 約 15–30 分鐘 | 約 45–100 分鐘 |

估計方式與假設：

- **本機實測**（Apple Silicon Mac，8 核，PPO 8 局同時跑）：每秒約 3,700–4,000 步；
  10 / 30 / 50 回合的實測時間分別約 3、9、15 秒（不含里程碑評估）。
- 時間有包含定期評估和里程碑評估（每次玩 5 局，agent 越強評估越久）。
- **Colab 是估計值**：免費版只有 2 個 CPU 核心，遊戲模擬大約只有本機的三分之一，實際速度請看 log 裡的 `steps/s`。
- 2000 回合的範圍很大，因為回合長度取決於 agent 學得多好；如果 agent 很強、每局都活很久，步數會更多。

---

## 網頁版（demo 用）

```bash
python scripts/export_web.py        # 把 models/ppo/best_model.zip 轉成 web/model/ppo_model.js
python -m http.server 8000          # 在專案根目錄開一個本機伺服器
```

打開 <http://localhost:8000/web/>（也可以直接用瀏覽器開 `web/index.html`，但字型和音效可能載入不完整）。

頁面做成街機機台的樣子，右邊的操作台可以：

- 「自己玩」/「AI 開車」切換
- 「直接打魔王」/「下一關魔王」，demo 時不用等雜魚
- x1 / x2 / x4 速度、「危險格」（看網路眼中的危險區域和它選的方向）、音效開關
- 「AI 對這一步的把握」：AI 選的動作的機率
- 顯示 AI 跑了幾局、平均幾分

網頁版的策略網路是用純 JavaScript 做矩陣乘法，不需要任何機器學習函式庫。
Safari 不支援 `.ogg` 音效，建議用 Chrome 或 Firefox。

---

## 專案結構

```
vertical-shmup/
├── setup.py / requirements.txt   安裝設定與相依套件
├── README.md / CREDITS.md        說明文件、素材來源
├── assets/                       所有素材（pygame 版和網頁版共用）
│   ├── images/                   player、enemies、projectiles、items、effects、backgrounds、ui
│   ├── sounds/                   sfx（音效）、music（背景音樂）
│   ├── fonts/
│   └── licenses/                 素材的原始授權檔
├── src/shmup/                    Python 套件
│   ├── __main__.py               `python -m shmup` 的進入點
│   ├── paths.py                  所有檔案路徑
│   ├── core/                     遊戲規則（不用 pygame）
│   │   ├── rules.py              所有可調整的數字（網頁版的 rules.js 由它產生）
│   │   ├── rng.py                可重現的亂數（xorshift32）
│   │   ├── entities.py           玩家、子彈、道具
│   │   ├── enemies.py            敵人和魔王的行為
│   │   ├── patterns.py           彈幕的發射方式
│   │   ├── director.py           出怪和魔王的時間安排
│   │   └── world.py              每個 frame 的更新和碰撞
│   ├── client/                   pygame 畫面、輸入、音效
│   └── agent/                    強化學習
│       ├── features.py           遊戲 → 284 維觀測、18 種動作
│       ├── env.py                gymnasium 環境（給 SB3 用）
│       ├── train.py              PPO 訓練、回合計數、里程碑存檔、評估、續訓
│       ├── policy.py             pygame 版和錄影用的推論
│       └── export.py             匯出規則和策略網路給網頁版
├── scripts/                      train_cpu.py、train_gpu.py、export_web.py、record_video.py
├── notebooks/                    train_on_colab.ipynb
├── web/                          網頁版（HTML5 Canvas + 純 JavaScript）
├── models/                       訓練出來的模型（不放進 git）
├── tests/                        測試，包含 Python 和 JavaScript 的一致性測試
└── docs/                         README 用的圖片
```

這樣分的原因：

- `core/` 只放遊戲規則、不碰畫面，所以訓練時可以不開視窗、跑得很快，網頁版也能逐行照著寫
- 所有數字只寫在 `rules.py` 一個地方，網頁版的 `rules.js` 是自動產生的，測試會檢查有沒有過期
- 自己寫亂數產生器，同一個 seed 在 Python 和瀏覽器會跑出完全一樣的遊戲
- 強化學習的演算法交給 SB3，我們只寫遊戲、環境和訓練流程（回合計數、存檔、評估）

---

## 測試

```bash
pip install -e ".[game,rl,dev]"
pytest
```

- `tests/test_agent.py` 用 SB3 內建的 `check_env` 檢查 gymnasium 環境寫得對不對
- `tests/test_world.py` 檢查遊戲規則（2 關、雙魔王、炸彈、護盾、ALL CLEAR 等）
- `tests/test_web_parity.py` 會用同一個 seed，分別在 Python 和 Node.js 跑 30,000 個 frame（兩關都會打到），
  檢查分數、子彈數、亂數狀態、觀測向量是否完全一樣，也會檢查匯出的 PPO 策略網路在 JavaScript 算出的
  動作機率和 PyTorch 一樣。沒有安裝 Node.js 時這個測試會自動跳過。

---

## 2022 年以前檢查

### 素材

| 素材 | 發布年份 | 檔案日期（原始壓縮檔內） | 授權 |
|------|---------|------------------------|------|
| Kenney Space Shooter Redux（戰機、敵人、魔王、雷射、道具、背景、字型、部分音效） | 2014 | 2013-11 ～ 2014-01 | CC0 |
| Kenney Digital Audio（撿道具、爆炸、炸彈、受傷音效） | 2012 | 2017-10（重新打包） | CC0 |
| Kenney Music Jingles（過關音效） | 2014 | 2014-03 | CC0 |
| Matthew Pablo《Orbital Colossus》（背景音樂） | 2013 | MP3 標籤年份 2013 | CC-BY 3.0 |

`docs/` 裡的圖片是這個遊戲自己的截圖。爆炸、星空、發光子彈等特效是程式畫出來的，沒有用額外的圖片。
完整來源見 [CREDITS.md](CREDITS.md)。

### 演算法

| 演算法 | 年份 |
|--------|------|
| PPO（Proximal Policy Optimization） | 2017 |
| GAE（Generalized Advantage Estimation） | 2015 |
| Actor-Critic（A3C / A2C） | 2016 |
| Adam | 2014 |
| xorshift 亂數 | 2003 |

### 函式庫與工具

| 名稱 | 第一次發布 | 這個專案用的版本 | 用在哪裡 |
|------|-----------|-----------------|---------|
| Stable Baselines3 | 2020 年（1.0 版 2021-03） | 2.x | PPO、多程序環境、訓練迴圈 |
| gymnasium | 2022-10（從 2016 年的 OpenAI Gym 分出來） | 1.x | 環境介面（`reset` / `step`） |
| PyTorch | 2016 | 新版 | SB3 的神經網路 |
| numpy | 2006 | 新版 | 觀測向量 |
| pygame | 2000 | 2.x | 只有自己玩、demo、錄影時用 |
| ffmpeg | 2000 | 任意 | 只有錄影時用 |
| 網頁版 | HTML5 Canvas、ES5 / ES2015、CSS Grid（2017） | — | 沒有任何外部 JavaScript 函式庫 |
| Google Colab | 2017 年推出 | — | 訓練環境 |

**版本說明（誠實版）**：Stable Baselines3 在 2022 年以前的版本（1.0 ～ 1.3）需要舊的 `gym 0.21`，
它在現在的 Python 3.13（以及 Colab 的 Python）上**裝不起來**。所以這個專案用的是新版 SB3 2.x + gymnasium，
但只使用 2022 年以前就發表的演算法（PPO 2017）和設定。
