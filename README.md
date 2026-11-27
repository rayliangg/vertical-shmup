# Vertical Shmup

縱向彈幕射擊遊戲，附帶一個用 **Stable Baselines3 的 PPO** 訓練的自動駕駛 agent，
會自己閃避敵人和子彈、撿道具、打魔王。有 **pygame 版**，也有免安裝的**網頁版**可以直接拿來 demo。

> 所有素材、演算法、套件都是 **2022 年 5 月 27 日以前**發布的，版本和日期見最後的「2022 年以前檢查」。

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rayliangg/vertical-shmup/blob/main/train_on_colab.ipynb)

**在 Colab 上用 GPU 訓練：** https://colab.research.google.com/github/rayliangg/vertical-shmup/blob/main/train_on_colab.ipynb

![遊戲畫面](docs/screenshots.png)

---

## 目錄

1. [快速開始](#快速開始)
2. [遊戲設計](#遊戲設計)
3. [從訓練到結果的流程](#從訓練到結果的流程)
4. [自動駕駛（PPO）](#自動駕駛ppo)
5. [在 Colab 上用 GPU 訓練](#在-colab-上用-gpu-訓練)
6. [在自己的電腦上訓練](#在自己的電腦上訓練)
7. [要訓練多少回合？](#要訓練多少回合)
8. [網頁版（demo 用）](#網頁版demo-用)
9. [專案結構](#專案結構)
10. [2022-05-27 以前檢查](#2022-05-27-以前檢查)
11. [素材來源](#素材來源)

---

## 快速開始

這個專案固定使用 2022 年 5 月以前的套件版本，需要 **Python 3.10**（新版 Python 裝不了 2022 年 5 月以前的套件）。
用 micromamba 0.23.3（2022-05-20）照 `env/` 裡的 lock file 開一個獨立的環境。lock file 把 Python 和它用到的底層函式庫
（openssl、sqlite、zlib…）每一個都固定成 2022-05-27 以前的版本，不會影響電腦上其他的 Python：

```bash
curl -sSL https://micro.mamba.pm/api/micromamba/osx-arm64/0.23.3 | tar -xj bin/micromamba   # Linux 把 osx-arm64 換成 linux-64
./bin/micromamba create -y -p ./py310 -f env/conda-osx-arm64.lock                            # Linux 用 env/conda-linux-64.lock
./py310/bin/python -m pip install --no-build-isolation -c requirements.txt gym==0.21.0
./py310/bin/python -m pip install -r requirements.txt
./py310/bin/python -m pip install --no-deps -e .
```

之後的 `python` 都是指 `./py310/bin/python`（也可以 `export PATH="$PWD/py310/bin:$PATH"`）。

之後所有功能都是 `python -m shmup <指令>`：

| 指令 | 做什麼 |
|------|-------|
| `python -m shmup play` | 自己玩（加 `--autopilot` 看 PPO 玩） |
| `python -m shmup train` | 訓練 PPO（不需要畫面；有 GPU 就用 GPU） |
| `python -m shmup report` | 學習曲線 + 第 100 / 500 / 2000 / 5000 回合模型的結果表 |
| `python -m shmup eval` | 用固定的 10 局評估一個模型 |
| `python -m shmup export` | 匯出遊戲規則和所有里程碑模型給網頁版（訓練時會自動做） |

每個指令都可以加 `--help` 看所有參數。

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

**彈幕遊戲的經典機制**：判定點只有 5 px、擦彈加分、被打中時如果還有炸彈會**自動放炸彈**抵銷、
被打之後有無敵時間、飛到畫面上方的「收點線」道具會自動吸過來。

### 魔王關卡

遊戲一共 **2 關**，每一關都是「雜魚波次（約 60 秒）→ WARNING → 魔王」，兩關打完就結束：

```
第 1 關：雜魚 → WARDEN（1 隻）
第 2 關：雜魚 → TWIN FANG（2 隻，一左一右）→ ALL CLEAR
```

| 關卡 | 魔王 | 第 1 階段 | 第 2 階段 | 第 3 階段 |
|------|------|-----------|-----------|-----------|
| 1 | WARDEN | Aimed Fans：五向自機狙 + 慢速大彈環 | Twin Spiral：雙螺旋 + 雷射 | Last Stand：密集環形彈 + 高速自機狙 |
| 2（最後一關） | TWIN FANG x2 | Crossfire：雙砲口交叉雷射 | Pinwheel：反向旋轉的風車彈 | Fang Rush：兩隻一左一右夾擊玩家 |

- 每隻魔王 HP 剩 66%、33% 時換階段，畫面上的子彈會被清掉，並顯示階段名稱
- 每個階段有 30 秒時限：時間內打破 +1000 分；時間到直接換下一階段；最後階段時間到魔王會逃走
- 第 2 關的兩隻 TWIN FANG 各自有血條和階段；**先打倒一隻，另一隻會暴走（RAGE），射速變 1.4 倍**
- 魔王 HP：WARDEN 300、TWIN FANG 每台 150（魔王 HP 一律是 50 的倍數）
- 整體難度已下調 15%（`DIFFICULTY_SCALE = 0.85`：射速、出怪速度、子彈速度），雜魚 HP 也下調約 15%
- TWIN FANG 另外再調弱：射速 x0.75、子彈速度 x0.85，Fang Rush 的自機狙間隔從 8 改成 14 frame
- 兩隻都打倒就 **ALL CLEAR**，加 20,000 分 + 每剩 1 滴血 5,000 分，遊戲結束

### 畫面風格

參考縱向彈幕射擊遊戲常見的版面（這個類型的共同慣例，不是照抄某一款遊戲）：
右邊資訊面板（HI-SCORE、SCORE、PLAYER、BOMB、POWER、GRAZE、STAGE、AI 搖桿燈號）、
上方魔王血條（階段刻度、倒數秒數）、底邊 ENEMY 標記、STAGE / WARNING / ALL CLEAR 標題帶。

![魔王](docs/bosses.png)

---

## 從訓練到結果的流程

```
[1] 遊戲規則  src/shmup/game/
     │   純 Python 模擬，不用畫面，同一個 seed 一定跑出同一局
     ▼
[2] gym 環境  src/shmup/rl/env.py、features.py
     │   每 2 個 frame 做一次決策（每秒 30 次）
     │   觀測：290 個數字（自機、最近 24 顆子彈、最近 8 個敵人、9x9 危險格、道具、2 隻魔王）
     │   動作：18 種（9 個方向 x 一般 / 慢速）
     │   獎勵：活著 +0.01、掉血 -1、吃道具 +0.05、打魔王、ALL CLEAR +5 …
     ▼
[3] 訓練  python -m shmup train（Stable Baselines3 PPO；Colab 用 GPU）
     │   ┌─▶ SubprocVecEnv：同時玩好幾局，每局一個程序，用滿所有 CPU 核心
     │   │     ▼
     │   │   每局走 1,024 步（GPU：2,048 步）→ 一批資料（依策略的機率抽樣動作 = 探索）
     │   │     ▼
     │   │   用 GAE 算每一步的 advantage（這個動作比平常好多少）
     │   │     ▼
     │   │   PPO 剪裁目標，同一批資料學 10 輪 → 丟掉，重新收集
     │   └─────┘
     ▼   每 100 萬步 / 第 100、500、2000、5000 回合
[4] 評估與存檔  固定 seed、選機率最高的動作玩 5 局（models/ppo/）
     │   ├─▶ best_model.zip        存活最久的模型
     │   ├─▶ last_model.zip        最新模型（斷線後 --resume auto 接著訓練）
     │   ├─▶ checkpoints/ppo_ep{N}.zip   第 100 / 500 / 2000 / 5000 回合的模型
     │   ├─▶ milestones.json、best.json   每個里程碑 / 最佳模型的紀錄（時間、步數、評估結果）
     │   ├─▶ web/ 和 專案的 web/model/   自動匯出的網頁版模型 + 選單清單（manifest.js）
     │   └─▶ part*.monitor.csv、config.json、versions.json   每回合紀錄、超參數、套件版本
     ▼   玩滿 5000 回合自動停止
[5] 報告  python -m shmup report
     │   ├─▶ report/learning_curve.png   學習曲線（總獎勵、存活時間、關卡）
     │   └─▶ report/results.md           里程碑模型 vs. 亂動 / 不動 兩個對照組
     ▼
[6] 看結果（這一步才需要畫面）
     ├─▶ 網頁：  web/compare.html，第 100 / 500 / 2000 / 5000 回合的 agent 在同一局一起玩（2x2）
     ├─▶ 網頁：  web/index.html，用選單選一個模型看它玩，或自己玩
     └─▶ pygame：python -m shmup play --autopilot
```

---

## 自動駕駛（PPO）

用 [Stable Baselines3](https://github.com/DLR-RM/stable-baselines3)（1.5.0，2022-03）的 **PPO**。選它的原因：

- **動作是 18 種離散選擇**：PPO 輸出每個動作的機率，剛好適合（SAC、TD3 是給連續動作的，不適用）。
- **遊戲模擬可以平行跑**：好幾個程序同時玩，PPO「需要大量資料」的缺點在這裡不是問題。
- **穩定、幾乎不用調參**：PPO 的剪裁讓每次更新只走一小步，訓練很少崩掉。
- **推論簡單**：demo 時只跑策略網路、選機率最高的動作，網頁版用純 JavaScript 就能算。

| 方法 | 出處 | 用途 |
|------|------|------|
| PPO（剪裁目標） | Schulman et al., 2017 | 主要演算法 |
| GAE（λ = 0.95） | Schulman et al., 2015 | 算 advantage |
| Actor-Critic | Mnih et al., 2016（A3C / A2C） | 策略網路 + 價值網路 |
| Adam | Kingma & Ba, 2014 | 優化 |
| 熵獎勵（entropy bonus） | Williams & Peng, 1991；Mnih et al., 2016 | 鼓勵探索 |
| 梯度裁剪（gradient clipping） | Pascanu et al., 2012 | 避免一次更新太大 |
| 正交初始化（orthogonal init） | Saxe et al., 2013 | 網路初始權重（SB3 預設） |
| frame skip（每 2 個 frame 決定一次） | Mnih et al., 2013 | 減少決策次數 |
| 學習率、clip 逐步降低 | Schulman et al., 2017（PPO 論文的 Atari 設定） | 後期穩定 |
| KL 提早停止（target_kl） | Achiam, 2018（OpenAI Spinning Up） | 一次更新不要改太多 |
| Wilson 信賴區間 | Wilson, 1927 | 報告的通關率誤差 |

- **網路**：策略網路 2 層 256 單元、價值網路 2 層 512 單元（tanh），共 557,075 個參數（網頁版只用策略網路，144,914 個）。
  之前試過兩邊都 3 層 512（1,358,355 個參數），通關率沒有變好，訓練卻慢了一倍多。
- **後期穩定**：前 500 萬步用學習率 2.5e-4、clip 0.2、熵係數 0.01，到 2000 萬步時平滑地降到 2.5e-5、0.1、0.002；
  另外一次更新的 KL 超過 0.03（target_kl 0.02 的 1.5 倍）就提早停。每次更新的 approx_kl、clip_fraction、entropy、
  最近 500 回合的通關率都記在 `models/ppo/train_stats.csv`，看得出訓練是真的在晃，還是只是評估的局數太少。
- **選最佳模型**：每 100 萬步用另外 20 局（seed 200000 起）評估，先比通關數、再比關卡、最後比存活時間。
  報告用的是另一組局（seed 100000 起），所以報告的數字不會因為「挑過」而偏高。
- **獎勵**：每步存活 +0.01、掉 1 滴血 -1、被迫自動放炸彈 -0.5、護盾破掉 -0.3、
  撿道具 +0.05、分數 x 0.0002、打中魔王一下 +0.003、打倒一隻魔王 +1、死亡 -1、ALL CLEAR +5。

詳細的原理和設計理由寫在 `README2.md`（個人筆記，沒有放進 git）。

---

## 在 Colab 上用 GPU 訓練

**Colab 網址：** <https://colab.research.google.com/github/rayliangg/vertical-shmup/blob/main/train_on_colab.ipynb>

1. 打開上面的網址，**執行階段 → 變更執行階段類型 → T4 GPU**。
2. 第一格是設定（回合數、里程碑、GPU、`USE_DRIVE`），需要的話先改。
3. 依序執行每一格：存放位置（Google Drive）→ 安裝 → 檢查 GPU → 快速測試 → **訓練** → 結果表 → 下載網頁版模型。
   - 程式碼會自動從 GitHub 下載，不用另外上傳。
   - **安裝**那格會另外裝 Python 3.10.4 和 2022 年 5 月以前的套件（Colab 內建的 Python 3.12 裝不了），約 3–5 分鐘。
4. `USE_DRIVE = True` 時，所有結果存在 `MyDrive/vertical-shmup/`。**斷線後**重新執行「存放位置」、「安裝」和「訓練」那幾格，
   `--resume auto` 會從最後一次存檔接著訓練，回合數也接著算。
   如果存檔是舊規則訓練的（觀測長度不一樣），`--resume auto` 會把舊的 `ppo/` 改名成 `ppo_old_obs284` 之類留著（不刪除），然後從頭訓練；
   報告和網頁匯出也會跳過這種舊模型。

**GPU 對這個專案的幫助有限**：瓶頸是 Python 的遊戲模擬（在 CPU 上跑），GPU 只加速「更新網路」那一步。
Colab 免費版只有 2 個 CPU 核心，所以通常比多核心的電腦慢；GPU 設定用比較大的 batch（1024）和每批資料（16384 步）來彌補。

---

## 在自己的電腦上訓練

```bash
python -m shmup train                              # 有 GPU 用 GPU 設定，沒有就用 CPU 設定
python -m shmup train --device cpu --n-envs 8      # 指定 CPU、同時 8 局
python -m shmup train --resume auto                # 有上次的存檔就接著訓練
python -m shmup report                             # 學習曲線 + 結果表
```

預設：同時玩「CPU 核心數」局（每局一個程序）、玩滿 **5000 回合**就停、
在第 **100 / 500 / 2000 / 5000** 回合存模型、每 100 萬步評估一次。**同一時間只跑一個訓練**，否則會搶同一批核心、寫到同一個資料夾。
Mac 上建議用 `caffeinate -i python -m shmup train`，訓練期間電腦不會睡著。

**每到一個里程碑，會自動存下這些紀錄**（不用手動做任何事）：

| 檔案 | 內容 |
|------|------|
| `models/ppo/checkpoints/ppo_ep{N}.zip` | 第 N 回合的模型 |
| `models/ppo/milestones.json` | 每個里程碑的回合數、步數、花了幾分鐘、存檔時間、評估結果（存活秒數、關卡、通關次數） |
| `models/ppo/best.json` | 目前最佳模型的同樣紀錄 |
| `models/ppo/web/`、`web/model/` | 網頁版模型（`ppo_ep100.js`…、`ppo_best.js`）和選單清單 `manifest.js` |
| `models/ppo/part*.monitor.csv` | 每一回合的總獎勵、長度、關卡（學習曲線用） |
| `models/ppo/train_stats.csv` | 每次更新的 approx_kl、clip_fraction、entropy、學習率、最近 50 / 500 回合的通關率 |

---

## 要訓練多少回合？

實際在一台 8 核心的 Mac（CPU 版設定、8 個環境）上跑完 5000 回合：**約 2,374 萬步、153.6 分鐘**（平均約 2,580 steps/s）。
下面是 `python -m shmup report` 的結果，每個模型都用同樣的 10 局（seed 100000～100009）評估：

| 模型 | 訓練到的時間 | 平均存活 | 平均分數 | 平均第幾關 | ALL CLEAR |
|------|-----------:|---------:|---------:|-----------:|----------:|
| 不動（對照組） | — | 33.9 秒 | 3368 | 1.00 | 0 / 10 |
| 亂動（對照組） | — | 39.4 秒 | 4026 | 1.00 | 0 / 10 |
| 第 100 回合 | 1.3 分鐘 | 62.5 秒 | 5744 | 1.00 | 0 / 10 |
| 第 500 回合 | 13.9 分鐘 | 192.5 秒 | 73329 | 1.80 | 5 / 10 |
| 第 2000 回合 | 61.7 分鐘 | 171.3 秒 | 57436 | 1.70 | 4 / 10 |
| 第 5000 回合 | 153.6 分鐘 | 173.7 秒 | 49087 | 1.80 | 2 / 10 |
| best_model（第 2640 回合） | 81.2 分鐘 | 191.0 秒 | 53288 | 1.80 | 3 / 10 |

觀察：

- **100 回合**：已經比亂動好，但還打不過第 1 關的 WARDEN。
- **500 回合**：已經學會躲子彈並打到第 2 關，一半的局可以 ALL CLEAR。學習速度最快的就是這一段。
- **2000、5000 回合**：沒有再變強，ALL CLEAR 次數反而上下震盪。這是 PPO 很常見的現象（policy 在幾種打法之間來回），
  所以訓練中會定期評估並另外保留 `best_model.zip`。
- 結論：**這個遊戲大約 500～2000 回合就夠用了**；5000 回合主要是拿來展示「練更久不一定更好」。
  想要更穩定，可以試著把 `--lr` 調小（例如 1e-4）或把 `--ent-coef` 調小，而不是單純加回合數。
- Colab T4（只有 2 個 CPU 核心）大約會慢 3～4 倍；TPU 執行階段要設 `DEVICE = "cpu"`，用它的多核心 CPU。

---

## 網頁版（demo 用）

訓練時每到一個里程碑就會自動把模型匯出到 `web/model/`，所以直接開網頁就好：

```bash
python -m http.server 8000          # 在專案根目錄開一個本機伺服器
```

有兩個頁面（直接用瀏覽器開也可以）：

- **<http://localhost:8000/web/compare.html>：四個 agent 一起比較。** 第 100 / 500 / 2000 / 5000 回合的 agent
  在**同一局**（同一個 seed）上同時玩，排成 2x2，每格即時顯示存活秒數、分數、第幾關，
  下面還有那個模型訓練時的評估結果。可以「重新開始」、「換一局」、暫停、x1 / x2 / x4 速度。
  還沒練到的回合會顯示 NOT TRAINED YET，訓練到了重新整理頁面就會出現。
- **<http://localhost:8000/web/>：自己玩，或選一個模型看它玩。**

訓練好的網頁版模型（`web/model/`）會放進 git，所以 clone 下來就能直接看；
在 GitHub 的 **Settings → Pages** 把來源設成 `main` 分支的根目錄，就能用
`https://rayliangg.github.io/vertical-shmup/web/compare.html` 在網路上直接看。
右邊的 **「AI 模型」選單**可以選要看哪一個：第 100 / 500 / 2000 / 5000 回合，或最佳模型；
選單下面會顯示那個模型練了幾步、測試時平均撐幾秒、平均打到第幾關、通關幾次。
換模型之後按「AI 開車」就能直接比較不同訓練程度的差別。

如果模型是在 Colab 上訓練的，把 `MyDrive/shmup/ppo/web/` 裡的檔案下載到專案的 `web/model/` 就行；
或是在本機執行 `python -m shmup export --run-dir <下載的 ppo 資料夾>` 重新匯出。

頁面做成街機機台的樣子，右邊的操作台也可以切換「自己玩」/「AI 開車」、
「直接打魔王」/「下一關魔王」、x1 / x2 / x4 速度、「危險格」、音效，並顯示 AI 對這一步的把握（動作機率）。
網頁版的策略網路是用純 JavaScript 做矩陣乘法，不需要任何機器學習函式庫。
Safari 不支援 `.ogg` 音效，建議用 Chrome 或 Firefox。

---

## 專案結構

```
vertical-shmup/
├── README.md                     說明文件（含素材來源）
├── requirements.txt              完整套件清單（全部 2022-05-27 以前的版本）
├── setup.py                      安裝設定
├── train_on_colab.ipynb          Colab GPU 訓練筆記本
├── src/shmup/
│   ├── __main__.py               命令列：play / train / eval / report / export
│   ├── paths.py                  所有檔案路徑
│   ├── game/                     【遊戲規則】純模擬，不用 pygame
│   │   ├── rules.py              所有可調整的數字（網頁版的 rules.js 由它產生）
│   │   ├── rng.py                可重現的亂數（xorshift32）
│   │   ├── entities.py           玩家、子彈、道具
│   │   ├── enemies.py            敵人、魔王、彈幕發射方式
│   │   ├── director.py           出怪和魔王的時間安排
│   │   └── world.py              每個 frame 的更新和碰撞
│   ├── rl/                       【強化學習】
│   │   ├── features.py           遊戲 → 290 維觀測、18 種動作
│   │   ├── env.py                gym 環境（獎勵設計）
│   │   ├── train.py              PPO 訓練、回合計數、里程碑存檔、續訓
│   │   ├── evaluate.py           評估、對照組、學習曲線、結果表
│   │   └── policy.py             載入模型做推論、匯出給網頁版
│   └── ui/                       【畫面】只有 play 會用到 pygame
│       ├── app.py                視窗、輸入、場景
│       ├── renderer.py           畫面、HUD、右側面板
│       ├── effects.py            粒子、星空等特效
│       └── assets.py             圖片、字型、音效
├── web/                          網頁版：index.html、style.css、js/（rules、core、agent、renderer、main）
├── assets/                       素材（圖片、音效、字型、授權檔）
└── docs/                         README 用的圖片
```

- `game/` 不碰畫面，訓練時完全不會 import pygame；網頁版的 `web/js/core.js` 是逐行對照它寫的
- 所有數字只寫在 `rules.py` 一個地方，網頁版的 `rules.js` 由 `python -m shmup export` 自動產生
- 強化學習演算法交給 SB3；`rl/` 只寫環境、訓練流程（回合計數、存檔、評估）和推論

---

## 2022-05-27 以前檢查

### 套件（`requirements.txt`，全部 2022-05-27 以前，日期是 PyPI 上該版本的發布日）

| 套件 | 版本 | 發布日期 | 用途 |
|------|------|---------|------|
| micromamba | 0.23.3 | 2022-05-20 | 建 Python 環境 |
| Python | 3.10.4 | 2022-03-24 | 全部 |
| stable-baselines3 | 1.5.0 | 2022-03-25 | PPO |
| gym | 0.21.0 | 2021-10-06 | 環境介面 |
| torch | 1.11.0（Linux 版內建 CUDA 10.2） | 2022-03-10 | 神經網路、GPU |
| numpy | 1.22.4 | 2022-05-20 | 觀測向量 |
| pandas / matplotlib | 1.4.2 / 3.5.2 | 2022-04 / 2022-05 | SB3 的相依、學習曲線 |
| pygame | 2.1.2 | 2021-12-27 | 自己玩（pygame 版） |
| pip / setuptools / wheel | 22.1.1 / 62.3.2 / 0.37.1 | 2022-05 / 2022-05 / 2021-12 | 安裝 |

其他間接相依（cloudpickle、pillow、packaging…）也全部固定在 `requirements.txt`，每一行都標了發布日期。
訓練時會把實際用到的版本寫進 `models/ppo/versions.json`。

**Python 底層的函式庫**（openssl、sqlite、zlib、tzdata、ncurses…）也固定了：`env/conda-osx-arm64.lock`、
`env/conda-linux-64.lock` 列出每一個 conda-forge 套件的網址和 md5，旁邊標了上傳日期，最新的是 2022-05-21。
這兩個檔案是先把 conda-forge 的套件索引過濾成「2022-05-27 23:59（台灣時間）以前上傳的」，再讓 conda 求解產生的。
（zlib 1.2.12 是 2022-05-27 UTC 晚上上傳的，台灣時間已經是 28 號，所以用 1.2.11。）

**gym 的安裝**加了 `-c requirements.txt`：不加的話，pip 會先把 numpy、cloudpickle 裝成最新版，下一步才降回來。

**唯一的例外：Colab 主機本身。** Colab 的作業系統、內建的 Python 3.12、GPU driver、`wget` 都是 Colab 提供的，
沒辦法換成 2022 年的版本。訓練只在另外裝的 Python 3.10.4 環境裡跑，不會用到 Colab 內建的 Python。

### 素材（逐檔比對）

`assets/` 裡每一個圖片、音效、字型、音樂檔，都和原始下載的壓縮檔**逐位元組相同**（用 SHA-1 比對），
檔案本身內嵌的日期也都在 2022 年以前（2007～2017）：

| 種類 | 原始檔案日期 | 檔案內嵌的資訊 |
|------|-------------|---------------|
| 圖片 32 個（戰機、敵人、魔王、子彈、道具、背景、UI） | 2014-01-29 | PNG 沒有內嵌時間 |
| 字型 2 個（kenvector_future） | 2013-11-15 | 字型檔記錄的建立 / 修改日期：2013-11-15；授權欄位寫 CC BY-SA 3.0 |
| 音效 11 個（.ogg） | 2014-01-29、2014-03-17、2017-10-28 | 編碼器 libVorbis 2007、2012 版 |
| 背景音樂（Orbital Colossus） | 2013-10-27 上傳 | MP3 標籤年份 2013 |

Space Shooter Redux 的圖片和音效是 CC0（公眾領域），不需要附授權檔；字型檔本身標的授權是 CC BY-SA 3.0，
所以字型照 CC BY-SA 3.0 標示作者（見下方「素材來源」）。

### 演算法

| 演算法 | 年份 |
|--------|------|
| PPO（Proximal Policy Optimization） | 2017 |
| GAE（Generalized Advantage Estimation） | 2015 |
| Actor-Critic（A3C / A2C） | 2016 |
| Adam | 2014 |
| 正交初始化 | 2013 |
| frame skip | 2013 |
| 梯度裁剪 | 2012 |
| 熵獎勵 | 1991 |
| KL 提早停止（target_kl） | 2018 |
| Wilson 信賴區間 | 1927 |
| xorshift 亂數 | 2003 |

### 網頁版

HTML5 Canvas、ES5 / ES2015 語法、CSS Grid（2017），沒有任何外部 JavaScript 函式庫。

---

## 素材來源

所有第三方素材都是 2019 年以前發布的。Kenney 兩個音效包的原始授權檔放在 `assets/licenses/`。

| 素材 | 作者 | 發布年份 | 授權 | 用在哪裡 |
|------|------|---------|------|---------|
| [Space Shooter Redux](https://kenney.nl/assets/space-shooter-redux) | Kenney | 2014 | CC0 1.0 | 戰機、敵人、魔王、雷射、道具、護盾、背景、UI、部分音效 |
| kenvector_future 字型（同一個素材包） | Kenney（用 FontStruct 製作） | 2013 | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)（字型檔內的授權欄位） | 介面文字 |
| [Digital Audio](https://kenney.nl/assets/digital-audio) | Kenney | 2012 | CC0 1.0 | 撿道具、爆炸、炸彈、受傷音效 |
| [Music Jingles](https://kenney.nl/assets/music-jingles) | Kenney | 2014 | CC0 1.0 | 過關音效 |
| [Orbital Colossus](https://opengameart.org/content/space-boss-battle-theme) | Matthew Pablo（[matthewpablo.com](http://www.matthewpablo.com)） | 2013 | [CC-BY 3.0](https://creativecommons.org/licenses/by/3.0/) | 背景音樂 |

CC0 不需要標示作者；CC-BY 3.0 和 CC BY-SA 3.0 需要標示作者，也就是上表的字型和音樂兩行。`docs/` 裡的圖片是這個遊戲自己的截圖。
