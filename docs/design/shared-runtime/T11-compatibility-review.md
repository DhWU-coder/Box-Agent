# T11 共享核心与桌面宿主兼容审查

## 审查方案

- 固定边界：本项只审查和记录，不修改产品源码、ACP 消息结构、模型配置或打包脚本。
- 保持行为的改动：建立 T1–T6 方案、源码入口、测试和客户端调用的对应关系。
- 功能变化：无；发现必须修复的问题时先补充独立方案，不将审查意见直接混入实现。
- 兼容影响：分别核对 ACP 前端、Python SDK、自定义委派工具、运行包与用户配置，不能以单一正常回合替代全部契约验收。
- 验收：核实消费登记、终止分类、容量异常、取消权限等待、委派预算和构建入口；以 T9/T10 验证作为证据并注明范围。
- 回退：删除本审查记录，不影响运行行为。

## 审查记录

## 结论

本轮共享核心修改不要求 officev3 前端新增 ACP 字段或修改正常流式消费方式。实际开发客户端已能处理容量错误和权限取消，见 [T10](T10-desktop-scenarios.md)。外部 Python SDK 与自定义委派实现有明确迁移要求，不能将“前端无需改动”推广为所有调用方完全无感。

| 对象 | 源码核对 | 兼容结论 |
| --- | --- | --- |
| CLI / ACP | cli 的 `_run_session_turn`、ACP 的 `AgentService().start` 与 `protocol_handle.events()` | 均使用同一交付机制，ACP 继续映射 payload，内部 envelope 不直接成为新线协议 |
| ACP 容量异常 | 既有请求错误响应；BoxAgentManager 的 prompt error 路径 | 实测客户端收到 error 而不是 done；前端无强制适配项 |
| Python SDK 结果消费 | AgentClient.run、AgentRunHandle.events/result | result 先登记后不再支持补读全部事件；调用方需要按 [SDK](SDK.md) 选择模式 |
| 运行结果 | RunResult.termination_kind、RunResultCollector | 旧 status/stop_reason 保留，新序列化字段可能影响严格字段白名单；正常回合并非用户目标验收 |
| 权限与取消 | PermissionBroker、CancellablePermissionNegotiator、Session.cancel | 沿用 ACP 反向请求；仅结果宿主必须提供有效权限处理，否则明确拒绝 |
| 自定义委派工具 | engine/execution 的 supports_delegated_budget 与调用上下文检查 | 配置硬委派预算时必须接入共享账本；否则明确拒绝。内置实现已支持 |
| 模型提供方 | ACP binding / SessionBoundLLM 入口未由本轮修改 | 第三方模型配置方式保留；本轮没有新增云端依赖 |
| 前端源码 | officev3 client-v2 工作区保持无改动 | 当前无必须随本轮提交的前端功能修改 |
| 打包 | scripts/build_runtime.py；客户端 install-box-agent-runtime、check-electron-build-resources | 沿用原流程，但必须产出包含本分支代码的 runtime 并更新打包输入，不能只打前端继续携带旧 runtime |

## 证据与仍然存在的边界

- T1–T6 的直接测试覆盖首次消费者登记竞争、等待者取消、权限处理、队列取消/关闭、超限、并发发布和共享预算。T9 记录最终完整门禁；T10补充真实客户端 IPC/ACP 链路。
- 前端此前检查结果为 181 passed、17 failed、1 skipped，其中 manager 108 passed；事件处理器和生命周期合计 17 项旧契约失败。它们不能计入 Box-Agent 门禁通过，也没有在本项擅自改写为绿色。未改客户端源码，本轮不重新宣称该前端全套测试通过。
- 浏览器/Canvas/字体等可选真实渲染环境和非 Windows 平台由 T9 单独列出；没有把平台跳过当作已验证。
- Python wheel/sdist 可构建不等于 standalone runtime 已安装。仍需按原流程构建目标平台 runtime、安装进客户端构建资源、构建/安装应用、重启并完成新的真实用户任务。当前仍停在开发版源码联调边界。
- 自动续跑判断的额外模型等待属于既有续跑策略，本轮未修改；正常目标完成判断和提供方等待优化应另立功能方案。

未发现需要为本轮共享运行契约强制修改前端线协议的证据；这不是对客户端其他既有缺陷或全部真实任务的无条件兼容保证。

### ACP 终态后的清理失败

ACP 收到 `DoneEvent` 后先关闭事件消费，再读取共享运行的最终结果，避免将终态后已发生的清理异常误报为成功。失败沿用现有 `session/prompt` 元数据：`ok=false`、`completed=false`、`runStatus=error` 和 `error` 消息；`stopReason` 仍使用协议允许的值，不要求宿主增加字段。

宿主关闭终态后的待清理句柄所产生的正常取消，仍保留原完成或等待原因。缺少 `DoneEvent` 的运行使用共享层的失败结果。相关回归覆盖立即清理失败、关闭期间清理失败、正常关闭、缺失终态及失败后同会话继续运行；这些检查证明源码 ACP 行为，不代表桌面安装包已经更新。
