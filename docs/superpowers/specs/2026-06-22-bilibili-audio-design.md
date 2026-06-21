# Bilibili 在线音频搜索与播放设计

**版本**: v0.4.0-beta  
**日期**: 2026-06-22  
**状态**: 已确认，待实现  

---

## 1. 目标

为 Holle Music 增加 **Bilibili 在线音频搜索与播放**能力：

- 用户在 `/search` 搜索歌曲时，若本地歌单无结果，自动搜索 Bilibili 视频并提取音频。
- 支持通过 AI 自然语言指令触发 B 站搜索，并根据意图自动播放或仅展示结果。
- 在线音频下载到本地缓存后播放，复用现有 `Player` 的进度条、频谱、切歌等全部能力。
- 缓存自动 LRU 清理，支持手动清空。
- 网络不可用时给出明确提示。

---

## 2. 范围

### 包含

- Bilibili 视频搜索（仅音频，不播放画面）。
- 音频下载与缓存管理。
- 终端 `/search` 命令扩展。
- 桌面宠物 `/search` 命令扩展。
- AI 工具扩展（`search_bilibili`、`play_song` 增强）。
- 自然语言意图处理（播放 vs 搜索）。
- 缓存命令 `/cache` / `/cache clear`。

### 不包含

- 视频画面播放。
- 除 Bilibili 之外的其他在线平台（YouTube、网易云、QQ 音乐等）。
- 用户登录 B 站获取高音质（仅使用匿名可访问的默认音质）。
- 歌词同步（在线音频暂不提供歌词）。

---

## 3. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 在线来源 | 仅 Bilibili | 聚焦、技术可行、用户群体明确。 |
| 播放方式 | 下载到缓存后播放 | 与现有 `pygame` 播放器完全兼容，无需更换后端。 |
| 搜索入口 | 扩展现有 `/search` | 保持用户习惯，本地优先，无结果自动 fallback。 |
| 结果标记 | 在线歌曲标题后加 `(web)` | 一眼区分本地与网络来源。 |
| 自动下载 | 搜索返回 10 条后全部后台下载 | 体验最流畅，点击任意结果都能尽快播放。 |
| AI 行为 | 智能判断 | 用户说“播放”自动播第一条；说“搜索”只展示结果。 |
| 缓存清理 | LRU 自动 + 手动 `/cache clear` | 自动无感，手动兜底。 |

---

## 4. 架构

### 4.1 新增模块

| 模块 | 路径 | 职责 |
|---|---|---|
| `bilibili_searcher` | `src/holle_music/bilibili_searcher.py` | B 站视频搜索、音频直链解析、元数据获取。 |
| `online_cache` | `src/holle_music/online_cache.py` | 缓存目录管理、命中查询、LRU 清理、损坏检测。 |

### 4.2 修改模块

| 模块 | 路径 | 修改内容 |
|---|---|---|
| `models` | `src/holle_music/models.py` | `Song` 增加 `source`、`bvid`、`web_url`、`cover_url` 字段。 |
| `settings` | `src/holle_music/settings.py` | 默认配置增加缓存相关项。 |
| `app` | `src/holle_music/app.py` | `/search` 本地无结果时搜 B 站；新增 `/cache`、`/cache clear`。 |
| `tui_tools` | `src/holle_music/tui_tools.py` | 新增 `search_bilibili` 工具；`play_song` 支持 B 站结果。 |
| `pet/commands` | `src/holle_music/pet/commands.py` | Pet 的 `/search` 同样支持 B 站 fallback。 |
| `pet/ai_tools` | `src/holle_music/pet/ai_tools.py` | Pet AI 工具同步扩展。 |
| `pyproject.toml` | 根目录 | 新增 `yt-dlp` 依赖；版本号更新为 `0.4.0-beta`。 |

### 4.3 数据流

```
用户输入 /search 周杰伦晴天
  ↓
app._search_songs() 先搜本地
  ↓
本地无结果
  ↓
bilibili_searcher.search("周杰伦晴天", max_results=10)
  ↓
yt-dlp 返回视频列表（标题 / UP主 / 时长 / bvid / 封面URL）
  ↓
转换为 Song 对象（source="bilibili", title 后附加 "(web)"）
  ↓
按原有歌单格式显示在 PlaylistPanel
  ↓
后台启动下载线程池（最多 3 并发），下载全部 10 条音频
  ↓
用户点击某条 / AI 调用 play_song
  ↓
online_cache.prepare(bvid) 检查缓存
  ↓
命中 → 直接播放
未命中 → 等待当前下载完成 → 播放
```

---

## 5. 数据模型扩展

### 5.1 `Song` 新增字段

```python
@dataclass(eq=False)
class Song:
    path: Path
    title: str = ""
    artist: str = "未知艺术家"
    album: str = "未知专辑"
    duration: float = 0.0
    source: str = "local"          # "local" | "bilibili"
    bvid: str = ""                 # B 站视频 ID
    web_url: str = ""              # B 站视频页面 URL
    cover_url: str = ""            # 封面图 URL（可能为空）
```

### 5.2 兼容性

- 本地歌曲这些新增字段保持默认值，现有序列化/反序列化不受影响。
- `Song.__eq__` 和 `__hash__` 仍基于 `path`，确保与现有播放器逻辑一致。
- IPC 传输到桌面宠物时，B 站歌曲的 `path` 在缓存下载完成前可设为空字符串；下载完成后更新为真实缓存路径。宠物端若收到未下载完成的 B 站歌曲，显示“下载中”而不是尝试播放。

---

## 6. 缓存设计

### 6.1 目录结构

```
~/.holle_music/cache/bilibili/
├── BV1xx411c7mD_0.m4a       # 音频文件
├── BV1xx411c7mD_0.m4a.part  # 下载中临时文件
├── BV1xx411c7mD.json        # 元数据
└── ...
```

### 6.2 元数据文件

```json
{
  "bvid": "BV1xx411c7mD",
  "title": "晴天",
  "artist": "周杰伦",
  "up": "某某UP主",
  "duration": 240.5,
  "web_url": "https://www.bilibili.com/video/BV1xx411c7mD",
  "cover_url": "https://...",
  "downloaded_at": 1719004800,
  "last_played_at": 1719009600
}
```

> 音频文件名中的 `{quality}` 暂固定为 `0`，表示匿名默认音质；后续若支持登录换音质可扩展。

### 6.3 命中规则

- 播放前检查 `{bvid}_{quality}.*` 是否存在且文件大小大于 0。
- 命中则直接播放，并更新 `last_played_at`。
- 下载中使用 `.part` 后缀，完成后重命名，避免播放半成品。
- 下载并发数：最多 3 个线程同时下载，避免占用过多带宽和 CPU。

### 6.4 自动清理

- 触发时机：每次新增下载完成时。
- 限制：
  - 默认最大占用 `1GB`
  - 默认最大文件数 `200`
  - 任一条件触发即清理。
- 算法：按 `last_played_at` 升序删除，直到低于限制。
- 配置持久化到 `settings.json`：
  ```json
  {
    "bilibili_cache_max_mb": 1024,
    "bilibili_cache_max_files": 200
  }
  ```

### 6.5 手动清理

- `/cache`：显示缓存占用和文件数。
- `/cache clear`：清空 `~/.holle_music/cache/bilibili/`。

---

## 7. 命令与 AI 集成

### 7.1 终端命令

| 命令 | 行为 |
|---|---|
| `/search <关键词>` | 先搜本地；无结果则搜 B 站，返回 10 条带 `(web)` 标记的结果并后台下载。 |
| `/search` | 恢复显示原始完整歌单。 |
| `/cache` | 显示 B 站缓存占用和文件数。 |
| `/cache clear` | 清空 B 站缓存。 |

### 7.2 Pet 命令

- `PetCommandHandler._cmd_search` 复用同样逻辑。
- 桌面宠物没有歌单列表，B 站结果通过气泡展示前几条，并提供“播放第 N 首”的快捷回复。

### 7.3 AI 工具

#### `search_bilibili`

```json
{
  "name": "search_bilibili",
  "description": "在 Bilibili 搜索视频音频。",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "搜索关键词"},
      "max_results": {"type": "integer", "default": 10}
    },
    "required": ["query"]
  }
}
```

#### `play_song` 增强

- 优先匹配最近本地搜索结果。
- 其次匹配最近 B 站搜索结果。
- 若匹配到 B 站结果，触发下载/播放流程。

### 7.4 自然语言意图

| 用户说法 | 行为 |
|---|---|
| “播放 周杰伦 晴天” | 先本地 → 无结果则 B 站 → 自动播放第一条。 |
| “搜索 周杰伦 晴天” | 先本地 → 无结果则 B 站 → 只展示结果。 |
| “B 站搜索 xxx” | 跳过本地，直接搜 B 站。 |

### 7.5 系统提示更新

给 DeepSeek/Ark 的系统提示增加：

- 如果用户想找的歌本地没有，调用 `search_bilibili`。
- 如果用户说“播放”，找到结果后必须调用 `play_song`。
- 如果用户说“搜索”，只返回结果，不调用 `play_song`。
- B 站结果在歌单中带有 `(web)` 标记。

---

## 8. 错误处理

| 场景 | 行为 |
|---|---|
| 网络不可用 | 提示“未找到本地歌曲，且无法连接网络搜索 B 站。” |
| B 站无结果 | 提示“本地和 B 站都未找到 ‘xxx’。” |
| 单个下载失败 | 列表项显示“下载失败”，不影响其他下载；点击提示重试。 |
| 缓存文件损坏 | 删除缓存，提示重新搜索播放。 |
| 切换搜索关键词 | 取消上一次搜索的未完成任务。 |
| 应用退出 | 停止所有下载线程。 |

---

## 9. UI 表现

### 9.1 歌单列表

在线歌曲显示为：

```
1. 晴天 (web) - 周杰伦
2. 七里香 (web) - 周杰伦
...
```

### 9.2 状态提示

- 搜索中：`正在搜索 Bilibili...`
- 下载中：`正在下载 B 站音频: 晴天 (1/10)`
- 下载完成：`晴天 下载完成`
- 下载失败：`晴天 下载失败: 网络超时`

### 9.3 封面

- `cover_url` 存在时尝试显示。
- 为空或获取失败时不显示封面，避免占位图影响体验。

---

## 10. 依赖

在 `pyproject.toml` 中新增：

```toml
dependencies = [
    ...,
    "yt-dlp>=2024.0.0",
]
```

`yt-dlp` 负责：
- B 站视频搜索（通过 `yt_dlp.YoutubeDL.extract_info` 配合搜索查询）。
- 音频流解析。
- 音频下载。

---

## 11. 测试计划

### 11.1 单元测试

- `tests/test_bilibili_searcher.py`：mock `yt-dlp` 返回，验证搜索解析、元数据转换、错误处理。
- `tests/test_online_cache.py`：验证缓存命中、LRU 清理、手动清理、损坏文件处理。
- `tests/test_models.py`：验证 `Song` 新增字段的序列化/反序列化。

### 11.2 集成测试

| 场景 | 预期 |
|---|---|
| 本地有结果 | `/search` 只返回本地，不触发 B 站。 |
| 本地无结果 + 有网 | 自动搜 B 站，显示 `(web)` 结果，后台下载。 |
| 本地无结果 + 无网 | 提示网络不可用。 |
| 点击已缓存项 | 立即播放。 |
| 点击下载中项 | 显示等待/下载中。 |
| AI “播放 xxx” | 本地无结果时自动搜 B 站并播放第一条。 |
| AI “搜索 xxx” | 只展示结果。 |
| `/cache clear` | 缓存目录清空。 |

### 11.3 边界情况

- B 站搜索返回少于 10 条：有多少下多少。
- 视频没有音频流：跳过并记录失败。
- 用户快速切换搜索词：取消旧任务。
- 缓存文件被手动删除：播放时自动重新下载。

---

## 12. 版本与发布

- `pyproject.toml` 版本更新为 `0.4.0-beta`。
- 更新 `README.md`：说明 B 站搜索播放功能、新增命令、缓存说明。
- 更新 memory 文件：新增 `bilibili_searcher`、`online_cache` 模块记忆，更新 `commands`、`pet` 相关记忆。

---

## 13. 风险与限制

| 风险 | 说明 |
|---|---|
| B 站接口变更 | `yt-dlp` 社区维护较及时，但仍可能短暂失效。 |
| ToS 合规 | B 站用户协议禁止未经授权抓取；本功能定位为个人本地工具，不建议商业分发。 |
| 下载流量 | 一次搜索最多下载 10 条音频，流量较大；已提供缓存上限配置。 |
| 音质限制 | 匿名访问默认音质，不登录无法获取高音质。 |

---

## 14. 后续可扩展

- 支持登录 B 站获取高音质。
- 支持在线音频歌词（通过 AI 识别或外部歌词 API）。
- 扩展至 YouTube / 网易云等其他平台（需单独评估合规性）。
