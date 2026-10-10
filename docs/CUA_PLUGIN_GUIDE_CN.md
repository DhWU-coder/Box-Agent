# CUA 插件使用指南

本文说明如何在 macOS 13+ Apple Silicon 上让 Box-Agent 通过 CuaDriver 的 MCP 服务使用桌面操作，并让支持图片输入的模型看到 CUA 截图。

本指南的适配基线是 **CuaDriver 0.32.0**，采用独立 `CuaDriver.app` 加 stdio MCP 的接入方式。工具及参数由 Box-Agent 从运行中的 Driver schema 读取；这里只固定安装版本和连接配置。

安装完成后的配置应对应以下关系：

| 项目 | 本指南使用的值 |
| --- | --- |
| Driver 版本 | `0.32.0` |
| MCP command | `/Applications/CuaDriver.app/Contents/MacOS/cua-driver` |
| MCP args | `["mcp"]` |
| MCP 服务名 / 插件 `server_name` | `cua-computer-use` |
| 模型图片能力 | 支持图片的模型显式设置 `image_input: true` |
| 插件截图输入 / 保存 | `feed_screenshots: true` / `persist_images: true` |

## 1. 运行前提

CUA 插件只负责 Box-Agent 内的 MCP 结果适配、图片注入和 sidecar 保存。它不包含 `cua-driver` 二进制，也不会替操作系统授予辅助功能或屏幕录制权限。

需要先准备以下运行时：

1. macOS 上已安装并能运行 `cua-driver`。
2. CuaDriver.app 已获得辅助功能和屏幕录制权限。
3. Box-Agent 的 MCP 配置能启动 CuaDriver 的 MCP 子命令。

已安装的用户先检查 App 内二进制版本；返回 `cua-driver 0.32.0` 时，可跳到权限检查和 MCP 配置，不需要重装：

```bash
/Applications/CuaDriver.app/Contents/MacOS/cua-driver --version
```

下面的安装脚本下载并校验 [CuaDriver 0.32.0 官方发布包](https://github.com/trycua/cua/releases/tag/cua-driver-rs-v0.32.0)，安装 CLI 和 `CuaDriver.app`。归档 SHA-256 为 `31f278f38015616a02142ccbb396721897cee4892927db103a31b297f60035a9`，与官方 release asset digest 一致。Box-Agent Python 包不包含这个 macOS 原生驱动。已有不同版本的 App 时，脚本会停止；升级步骤见下文。

```bash
cat > /tmp/install-cua-driver.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

[[ "$(/usr/bin/uname -s)" == "Darwin" && "$(/usr/bin/uname -m)" == "arm64" ]] || {
  echo "This installer requires Apple Silicon macOS." >&2
  exit 2
}
[[ "$(/usr/bin/id -u)" == "0" ]] || {
  echo "Run with: sudo bash /tmp/install-cua-driver.sh" >&2
  exit 2
}

version="0.32.0"
url="https://github.com/trycua/cua/releases/download/cua-driver-rs-v${version}/cua-driver-rs-${version}-darwin-arm64.tar.gz"
sha256="31f278f38015616a02142ccbb396721897cee4892927db103a31b297f60035a9"
prefix="/usr/local/lib/cua-driver-${version}"
cache="/usr/local/lib/cua-driver-downloads"
archive="${cache}/cua-driver-rs-${version}-darwin-arm64.tar.gz"

/bin/mkdir -p "${cache}" /usr/local/bin
if [[ ! -f "${archive}" ]]; then
  /usr/bin/curl --fail --location --retry 5 --output "${archive}.partial" "${url}"
  /bin/mv "${archive}.partial" "${archive}"
fi
printf '%s  %s\n' "${sha256}" "${archive}" | /usr/bin/shasum -a 256 -c -

if [[ ! -f "${prefix}/.installed" ]]; then
  /bin/mkdir -p "${prefix}"
  /usr/bin/tar -xzf "${archive}" -C "${prefix}" --strip-components 1
  [[ -x "${prefix}/cua-driver" && -d "${prefix}/CuaDriver.app" ]] || {
    echo "Unexpected CuaDriver package layout." >&2
    exit 5
  }
  /usr/bin/codesign --verify --deep --strict "${prefix}/CuaDriver.app"
  /usr/bin/touch "${prefix}/.installed"
fi

if [[ -d /Applications/CuaDriver.app ]]; then
  current=$(/usr/bin/shasum -a 256 /Applications/CuaDriver.app/Contents/MacOS/cua-driver | /usr/bin/cut -d ' ' -f 1)
  expected=$(/usr/bin/shasum -a 256 "${prefix}/CuaDriver.app/Contents/MacOS/cua-driver" | /usr/bin/cut -d ' ' -f 1)
  [[ "${current}" == "${expected}" ]] || {
    echo "An existing CuaDriver.app has a different binary; stop and back it up before rerunning (see the upgrade steps)." >&2
    exit 6
  }
else
  /usr/bin/ditto "${prefix}/CuaDriver.app" /Applications/CuaDriver.app
fi
/usr/bin/codesign --verify --deep --strict /Applications/CuaDriver.app
/bin/ln -sfn "${prefix}/cua-driver" /usr/local/bin/cua-driver
/Applications/CuaDriver.app/Contents/MacOS/cua-driver --version
/usr/local/bin/cua-driver --version
echo "Installed CuaDriver ${version}. Grant Accessibility and Screen Recording permissions, then start CuaDriver.app."
SH
sudo bash /tmp/install-cua-driver.sh
```

### 从旧版升级

先结束桌面操作任务并退出使用该 Driver 的 Box-Agent CLI / ACP 宿主，再停止旧 Driver、备份 App。以下命令保留旧 App，随后重新运行上面的安装脚本：

```bash
/Applications/CuaDriver.app/Contents/MacOS/cua-driver stop
task_cua_backup="/Applications/CuaDriver.app.backup-$(date +%Y%m%d-%H%M%S)"
sudo mv /Applications/CuaDriver.app "${task_cua_backup}"
sudo bash /tmp/install-cua-driver.sh
```

升级后重新检查权限，并重启 Box-Agent 或承载 ACP 的应用。只替换磁盘文件不会让已经运行的 MCP / ACP 进程加载新版本。

### 权限与启动检查

以当前登录的桌面用户执行权限引导和状态检查，不要使用 `sudo`：

```bash
/Applications/CuaDriver.app/Contents/MacOS/cua-driver permissions grant
/Applications/CuaDriver.app/Contents/MacOS/cua-driver permissions status --json
```

`permissions grant` 通过 LaunchServices 启动 App 并引导授权；按系统提示允许辅助功能和屏幕录制。`permissions status` 是只读检查，需确认 `accessibility` 和 `screen_recording` 为 `true`，且 `source` 指向 Driver daemon 的 `com.trycua.driver` 身份。没有运行中的 daemon 时可能返回 `unknown`；权限布尔值也不能代替真实截图验收。

需要手动启动驱动时，使用 App 身份启动：

```bash
open -g -a /Applications/CuaDriver.app --args serve
/Applications/CuaDriver.app/Contents/MacOS/cua-driver status
```

配置下文的 MCP server 后，`mcp` 代理也可以自动拉起独立 App。本指南不添加 `--direct` 或 `--embedded`：这些模式改变运行时和 macOS 权限归属，不能作为此安装方式的直接替代。`/usr/local/bin/cua-driver` 是安装脚本提供的可选 CLI 链接；MCP 示例直接使用 App 内绝对路径，不依赖 PATH。

## 2. 配置 CuaDriver MCP 服务

Box-Agent 默认读取 `~/.box-agent/config/mcp.json` 和 `~/.box-agent/config/config.yaml`。开发目录中的模型配置可能优先，ACP 宿主也可能指定其他配置来源；可以用 `box-agent config --json` 查看 CLI 实际读取的模型配置路径。在已有 `mcpServers` 下合并以下 stdio server，保留其他服务；`cua-computer-use` 是服务名，后面插件配置中的 `server_name` 必须与它一致：

```json
{
  "mcpServers": {
    "cua-computer-use": {
      "description": "Local CuaDriver computer-use MCP",
      "type": "stdio",
      "command": "/Applications/CuaDriver.app/Contents/MacOS/cua-driver",
      "args": ["mcp"],
      "alwaysLoad": true,
      "disabled": false,
      "connect_timeout": 60,
      "execute_timeout": 120
    }
  }
}
```

如果驱动安装在其他位置，只替换 `command`，不要把 `cua-driver` 的路径写进 `config.yaml`。`mcp.json` 中的 `disabled` 必须为 `false`；修改后重新启动 Box-Agent，让既有 MCP loader 建立连接。

## 3. 开启 Box-Agent CUA 插件

在 Box-Agent 的 `~/.box-agent/config/config.yaml` 中加入：

```yaml
plugins:
  cua:
    server_name: "cua-computer-use"
    feed_screenshots: true
    persist_images: true
```

把上述片段合并进现有 `plugins`，保留其他插件。这里的 `server_name` 必须匹配 `mcp.json` 的键名。如果已有服务名是 `cua` 或 `computer-use`，可以保留原名并让两处一致，不要为同一 Driver 重复创建服务。插件默认服务名为 `computer-use`，所以使用本指南的名字时必须显式填写。插件启动后会自动激活这个 server 已发现的工具，不需要模型先调用 `tool_search`；连接和重连仍由 Box-Agent 原有 MCP loader 管理。

CUA 插件是显式可选的：

- 没有 `plugins.cua` 命名空间时，插件不会激活。
- `feed_screenshots: false` 时保留工具文本和结构化状态，不注入截图。
- `persist_images: true` 时，有 SessionLog 的会话会把截图保存为图片 sidecar；该开关独立于视觉输入和模型能力。设为 `false` 可关闭插件图片落盘。
- 设置 `BOX_AGENT_CUA_VISION=false` 可以临时关闭图片注入，不改配置文件。
- 关闭插件不会卸载或停止已经安装的 CuaDriver；要停止 MCP 服务，应把 `mcp.json` 中对应 entry 设为 `disabled: true` 或移除它。

## 4. 模型识别和图片注入

插件不会仅因为模型名称看起来像视觉模型就无条件发送图片。它按以下顺序读取模型的图片输入能力：

| 检查来源 | 结果 |
| --- | --- |
| LLM adapter 的 `supports("image_input")` | 明确返回 `true` 或 `false` 时优先使用 |
| LLM adapter 的 `capabilities["image_input"]` | 明确声明时使用 |
| 当前模型候选的 `tags` 包含 `vision` | 判定为支持图片 |
| 模型名包含 `vision` 或 `deepseek-vl` | 作为兼容性启发式判定为支持 |
| DeepSeek API 或 `deepseek-*` 文本模型 | 判定为不支持 |
| 其他情况 | 能力未知，不发送图片 |

只有最终结果为 `true` 时，CUA 截图才会进入下一次模型请求。结果为 `false` 或 `None` 时，模型仍能看到 CUA 工具返回的文本状态，但不会收到图片。这是为了避免把图片块发送给普通文本模型。

截图保留 Driver 返回的字节和像素尺寸，Box-Agent 不再进行二次缩放。模型上下文会同时包含图片所属工具调用、参数和返回的捕获身份。截图明确无效或采集失败时只保留工具状态；下一次请求消费图片后，后续请求不会自动复用旧截图。

如果接入自定义模型，推荐在 LLM adapter 或模型目录中明确声明 `image_input: true`，或给对应模型候选增加 `vision` tag；不要依赖模型名称猜测。

### 在 `config.yaml` 登记自定义模型的图片能力

对于 OpenAI 兼容的自定义网关（例如 TokenHub），可以在主模型配置中显式登记能力。当前 Box-Agent 的 `config.yaml` 使用顶层模型字段，因此这里写成 `image_input`，不是再包一层 `llm:`：

```yaml
api_base: "https://tokenhub.sensetime.com/v1"
provider: "openai"
model: "你的模型名"
api_key: "YOUR_TOKENHUB_API_KEY"
image_input: true
```

`api_key` 只应保存在本机配置或 `auth.json`，不要把真实 key 提交到仓库。配置写入后，可以先确认 Box-Agent 读取到了声明：

```bash
box-agent config --json | jq '{config_file, model: .llm.model, image_input: .llm.image_input}'
```

`image_input` 只接受布尔值：

- `true`：允许 CUA 插件把最新截图作为图片输入发送给该模型；
- `false`：明确禁止图片输入，即使模型名包含 `vision` 也不会注入截图；
- 不写该字段：按上面的 adapter、模型候选和兼容性规则判断；最终能力仍未知时不发送截图。

该字段用于 CLI 和 ACP 默认模型 client，并随 `for_model` 绑定保留。ACP 宿主使用模型 profile 时，还需满足下文的 profile 能力规则。它只是 Box-Agent 对模型能力的声明，不会探测或修改服务端模型能力；填写 `true` 前应先确认该模型的接口确实接受 OpenAI 风格的图片消息。API 的 `/models` 返回能力元数据时，也需要由操作者核对具体模型是否支持图片输入，Box-Agent 不会自动把任意 `image` 字段转换成该声明。

### ACP 会话使用模型 profile 时

ACP 的 profile 绑定会创建独立模型 client。图片能力按以下规则传递：

1. 宿主生成的 profile 可显式提供布尔字段 `imageInput`；该声明对 profile 的 `defaultModel` 生效，`false` 也会保留并优先于主模型配置。
2. profile 没有对当前模型声明能力时，只有其 **provider、API 地址和会话选中的 model** 都与 `config.yaml` 默认 client 一致，才继承该 client 显式声明的 `image_input`。API 地址末尾的 `/` 不影响匹配。
3. 切换到不同模型、provider 或接口时，不继承其他模型的声明；该模型按自身能力规则判断。profile 的 `imageInput` 不自动扩展到同一接口下的其他模型。

例如，当前 ACP 会话与 `config.yaml` 都选择相同接口上的 `gpt-5.6-sol/azure_L/sfa`，顶层设置 `image_input: true` 后，匹配的 profile client 会保留该声明。若宿主管理另一模型，需在宿主生成对应 profile 时声明其能力，例如以下 profile 字段：

```json
{
  "defaultModel": "你的视觉模型名",
  "imageInput": true
}
```

这只是 profile 字段片段，不是完整 registry。模型 profile revision 由宿主管理，不要手工覆盖生成的 registry 或修改已有 revision。使用这些规则需要包含该修复的 Box-Agent runtime；更新源码后，需重新构建、安装并重启 ACP 宿主，再新建会话验收。`box-agent config --json` 显示默认模型配置，不能单独证明宿主 profile 会话的实际能力。

### 三个边界为什么需要同时存在

这次实现把图片能力拆成三个边界，各自解决不同问题：

1. **模型配置的 `image_input` 参数**：模型名称无法可靠证明接口是否接受图片。显式能力参数让 CLI、ACP 和 CUA 插件使用同一个判断结果，避免把图片误发给文本模型，也避免在不同入口重复维护模型识别逻辑。
2. **CUA 插件**：截图只属于配置的 CUA MCP 服务，不应让通用 MCP loader 认识 CuaDriver、sidecar 目录或 CUA 开关。插件负责服务激活、截图规范化、能力门控和 sidecar 生命周期，关闭插件时普通 MCP 和默认 Agent 路径保持不变。
3. **MCP result hook**：MCP loader 只能看到远端返回的 text/image content，不能把 CUA 规则硬编码进通用工具。run-scoped hook 将匹配的 CUA 图片转换成当前请求的一次性 transient user 内容，并把 sidecar 路径追加到普通 tool 结果；这样图片不会进入 durable user history，也不会污染其他 MCP server 的结果。

TokenHub 当前的模型目录可能只返回模型 ID 和 endpoint 类型，不一定带 `image` 字段。对实际模型发一条带 `image_url` 的最小 `chat/completions` 请求并得到成功响应，才是登记 `image_input: true` 的依据；不能因为模型能生成图片，就推断它能接收图片。

### 最小端到端验收

重启 Box-Agent 后先检查 Driver 版本、权限及模型配置：

```bash
/Applications/CuaDriver.app/Contents/MacOS/cua-driver --version
/Applications/CuaDriver.app/Contents/MacOS/cua-driver permissions status --json
box-agent config --json | jq '{config_file, model: .llm.model, image_input: .llm.image_input}'
box-agent doctor
```

`box-agent doctor` 的 MCP 检查只确认配置文件存在，不证明 Driver 连接、截图或模型视觉输入成功。然后运行 `box-agent`，发送“使用 CUA MCP 读取当前窗口并描述截图内容”。若使用 ACP，在重启后的宿主中新建会话执行同样的任务；CLI 检查不能代替 ACP 宿主验收。

验收时分别检查：

1. **工具连接与状态**：会话实际调用 Driver 工具，返回当前窗口状态；启用插件后结构化结果包含真实工具名、参数及 `structuredContent`。
2. **截图保存**：启用 `persist_images` 且会话有 SessionLog 时，工具结果的 `raw_output.mcp_image_references` 引用实际存在的图片文件，哈希和尺寸与本次返回一致。
3. **模型图片请求**：支持图片且开启输入时，工具后的下一次请求携带匹配的图片；后续请求不会自动累积旧图片。图片落盘、路径出现在文本或模型自称看到了截图，都不能单独证明请求携带了图片。以能保留图片输入信息的请求记录核对；若记录只保留文本或省略图片字段，这项仍待验证。

若只看到工具文本而没有图片，先检查 `image_input`、`server_name` 和 MCP 权限。

### 0.32.0 观察与动作约定

Box-Agent 使用 Driver 实际声明的工具 schema，插件补充动作依据说明：

- 元素动作使用目标窗口最新观察的 `element_token`；新观察替换旧快照后，不继续使用失效 token。
- 支持 `target` 的工具使用 `target` 或旧 `pid/window_id/scope` 字段之一，不能混用。
- `screenshot_frame` 是返回截图的像素坐标，`frame` 是桌面屏幕坐标；每个动作按其工具 schema 的坐标约定执行。
- 像素动作消费 capture ID，后续动作取得新观察。`effect: unverifiable` 或派发成功后仍需观察结果。
- `window_id_not_found` 时重新枚举窗口；`window_owner_pid_mismatch` 时按返回的真实 owner PID 核对目标，尤其是打开/保存面板。

## 5. 图片保存和请求行为

一次 CUA 工具调用返回图片后，保存和模型输入独立控制：

1. 开启 `persist_images` 且有 SessionLog 时，把保留 Driver 原始字节和尺寸的图片写入当前 session 目录的 `images/<sha256>.<ext>` sidecar。
2. 把 `images/<sha256>.<ext>` 路径追加到 MCP 工具结果文本，让普通 tool message 进入 live Surface 和 SessionLog。
3. 开启 `feed_screenshots`、模型明确支持图片且截图有效时，把图片作为当前轮的 transient `user` 消息发送一次；它不进入 durable Surface，也不需要 provider hydrate。模型不支持图片时仍可独立保存 sidecar。

已成功保存到 sidecar 的图片不再把 base64 写入工具结果；SessionLog 保留图片路径、哈希和尺寸。未成功保存的图片保留原有 MCP raw output，避免丢失数据。`~/.box-agent/log/sessions/` 下的文件是诊断 SessionTrace，主要记录 LLM/tool 请求；要检查工具结果路径，应查看对应的 `~/.box-agent/sessions/<session>/session.jsonl`。

## 6. 常见问题

### MCP 工具没有出现

检查 `tools.enable_mcp` 是否开启、`mcp.json` 的 `disabled` 是否为 `false`、`command` 是否可执行，并确认 `server_name` 与插件配置一致。

### 工具成功但模型没有看到截图

依次检查：

1. `plugins.cua.feed_screenshots` 是否为 `true`。
2. 是否设置了 `BOX_AGENT_CUA_VISION=false`。
3. 当前 LLM 是否声明 `image_input: true`；未知能力会按文本模型处理。
4. CuaDriver 返回的图片是否是 MCP image block。
5. 是否返回 `screenshot_frame_valid: false` 或 `screenshot_error`；插件不会注入这类无效截图。

### 升级后仍连接旧版本

检查 `mcp.json` 的 `command` 指向哪个二进制，再对该绝对路径执行 `--version`。同时确认旧 daemon 已停止、Box-Agent / ACP 宿主已重启；终端 PATH 中另一个 `cua-driver` 的版本不能证明 MCP 使用的版本。源码改动也不会自动进入已打包的 ACP runtime，需重新构建、安装并重启消费它的宿主后验收。

### 普通模型收到了图片错误

这是模型能力声明不准确造成的。为该 LLM adapter 明确返回 `supports("image_input") == false`，或将其 `capabilities["image_input"]` 设置为 `false`。插件随后只保留工具文本。

### 如何完全关闭 CUA

执行以下任一项即可停止图片注入：移除 `plugins.cua`，设置 `feed_screenshots: false`，或设置 `BOX_AGENT_CUA_VISION=false`。如果还要停止 CuaDriver MCP 连接，将 `mcp.json` 中的 `cua-computer-use` entry 禁用并重启 Box-Agent。这个操作不会保证独立的 CuaDriver app daemon 退出；要完全停止驱动，再执行：

```bash
/Applications/CuaDriver.app/Contents/MacOS/cua-driver stop
```
