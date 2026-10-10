# CUA 插件配置与启动边界

完整的安装、MCP 配置、模型能力识别和排错步骤见
[CUA 插件使用指南](CUA_PLUGIN_GUIDE_CN.md)。本文保留插件边界和实现约束，供开发者阅读。

CUA 是可选插件。Box-Agent 核心只读取并保留通用的 `plugins` 命名空间，具体字段由 CUA 插件自己校验；核心 `tools` 配置不包含 `cua` 字段。

安装指南以 CuaDriver **0.32.0** 的独立 App / MCP 模式为基线：`mcp.json` 的 command 为 `/Applications/CuaDriver.app/Contents/MacOS/cua-driver`，args 为 `["mcp"]`，示例服务名为 `cua-computer-use`。安装 Driver、配置 MCP 和启用插件是三个独立步骤。

## 配置示例

```yaml
api_key: "sk-..."
api_base: "https://api.openai.com/v1"
model: "gpt-4o"
provider: "openai"
image_input: true

plugins:
  cua:
    server_name: "cua-computer-use"
    feed_screenshots: true
    persist_images: true
```

`Config.from_yaml()` 会把每个 `plugins.<name>` 保留为一个映射，不解释未知插件的字段。CUA 插件激活时再校验自己的命名空间：`server_name` 默认是 `computer-use`，`feed_screenshots` 和 `persist_images` 默认是 `true`，未知字段会被拒绝。`persist_images` 控制会话图片 sidecar，与模型是否支持图片及视觉输入开关独立。

示例显式覆盖默认服务名，必须与 `mcp.json` 的键名一致。`image_input` 是顶层模型能力声明，只对确认支持图片的模型开启。

没有 `plugins.cua` 命名空间时，虽然 bundled catalog 可以发现插件，CUA 运行绑定保持关闭；只有配置该命名空间后才会在对应 run 中启用。

## 启动链路

启动时由显式的插件装配目录注册内置可选插件：

```text
Config.from_yaml()
  -> Config.plugins（核心只做通用 YAML 透传）
  -> plugins/catalog.py（显式登记 CUA）
  -> PluginRuntime（默认包含 bundled plugins）
  -> PluginSession.open_run()
  -> CUA 插件读取 plugins.cua 并校验
```

需要完全排除可选内置插件的宿主可以构造 `PluginRuntime(include_bundled_plugins=False)`；这不会影响核心内置插件。

CUA 仍然需要在 `mcp.json` 中配置对应的 MCP 服务；插件启动后会通过已有的 MCP exposure manager 自动激活该 `server_name` 下已发现的工具，不需要模型先调用 `tool_search`。MCP 连接仍由既有 loader 负责，若服务尚未连接，插件不会绕过 loader 自己创建第二条连接。

## MCP 结构化结果

MCP loader 保留 `structuredContent` 为 `raw_output.mcp_structured_content`，成功和错误返回均适用。CUA 插件将配置服务的实际工具名、参数和结构化结果追加到工具文本；窗口、capture、snapshot、坐标空间及截图错误等字段按照 Driver 原始返回保留。其他 MCP 服务的模型文本投影保持原有路径。

针对 Driver 0.32 的窗口观察，插件补充动作依据说明：使用最新元素 token；`target` 与旧的 `pid/window_id/scope` 参数不能混用；`screenshot_frame` 是截图像素，`frame` 是屏幕坐标，动作遵循各工具实际声明的坐标合同。像素动作消费 capture ID，后续动作重新观测；工具已派发或 `effect: unverifiable` 都需要新状态确认任务结果。

## 图片注入条件

截图通过 MCP 工具结果进入运行时 Surface，但只有模型明确声明支持图片输入时才会写入图片消息：

| 模型图片输入能力 | 下一次请求 |
| --- | --- |
| `True` | 写入规范化图片块，并保留工具文本结果 |
| `False` | 不写入图片，只保留文本结果 |
| `None`（能力未知） | 不写入图片，只保留文本结果 |

普通模型或能力未知的模型只接收文本工具结果。启用 `persist_images` 且会话有 SessionLog 时，工具文本可以包含已保存的图片路径，路径本身不表示模型已经看到图片。图片能力判断、MCP 服务名匹配以及截图编码都属于 CUA 插件边界，核心 MCP 加载器不硬编码 CUA 逻辑。

图片块由插件写入会话目录的 `images/<sha256>.<ext>` sidecar，同时把路径追加到 MCP 工具结果文本。`raw_output.mcp_image_references` 保留图片引用、哈希、字节数与尺寸；已经由引用覆盖的图片字节不再重复写入 raw_output。未成功保存的图片仍使用原有 raw_output 路径。

图片输入沿用当前轮的 transient `user` 通道，只发送到工具调用后的下一次模型请求，不进入 durable Surface，也不在后续请求自动重放。插件保留 Driver 图片的原始字节、方向和尺寸，避免二次缩放改变像素依据；附带说明将图片与服务、工具、参数及实际返回的捕获身份关联。Driver 明确返回 `screenshot_frame_valid: false` 或 `screenshot_error` 时不注入该批图片，工具结构化状态仍然保留。

图片预算继续由已有 ContextEngine / transient 校验控制。需要减小输入时，通过运行中 Driver 工具实际提供的截图尺寸参数重新观测，使用该次返回的坐标信息。文件路径或 capture ID 本身不会触发自动读取文件、恢复旧截图或重放动作。
