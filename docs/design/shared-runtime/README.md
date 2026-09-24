# 桌面共享 Runtime 首轮实施

基线：`bf241c95fc8a0dc93771da99cb1ec846f2fb3a2e`。分支：`feat/shared-agent-runtime`。

按 T1–T6 顺序实施，每项方案、代码、测试和验证记录组成一个提交。固定边界是必须保留的契约；功能变化独立标注。当前范围是桌面共享运行边界、终止语义、事件容量和委派硬预算，不包含云端部署或语言迁移。

| 任务 | 分类 | 方案 |
| --- | --- | --- |
| T1 事件通道与结果聚合 | 保持行为的边界收敛 | [T1](T1.md) |
| T2 终止分类 | 增量接口行为 | [T2](T2.md) |
| T3 消费模式 | 消费生命周期行为 | [T3](T3.md) |
| T4 容量与背压 | 资源限制行为 | [T4](T4.md) |
| T5 委派共享硬预算 | 执行预算行为 | [T5](T5.md) |
| T6 桌面适配回归 | 集成验证 | [T6](T6.md) |

提交前检查目标 diff、暂存 diff 和工作区，使用明确路径暂存。最初交付止于源码、测试和可构建包；后续按用户授权增加开发版启动、重启与联调。不推送、不替换正式安装版。

## 评审入口

[优化任务总览](ROADMAP.md)列出 14 个模块、与原评估章节的对应关系、已完成范围及后续工作顺序。

先读各任务的“修改方案”，再对照提交和“实施与验证”。[SDK 使用及兼容迁移](SDK.md)说明消费模式、错误、权限和终止字段；[T6 验证记录](T6.md)区分直接回归、全量失败和运行时边界。

| 任务 | 提交 | 主要代码 |
| --- | --- | --- |
| T1 | db081ec | run_events、run_result、agent_run |
| T2 | 50b7953 | api/run、api 导出、sdk |
| T3 | e524c97 | agent_run、run_control |
| T4 | cc8df2d | api/delivery、run_events、agent_service、sdk |
| T5 | a6b3320 | tools/delegated_budget、tools/engine、sub_agent_tool |
| T6 | f4f03e8 | ACP/Session 取消接点、共享权限等待、SDK 仅结果入口、集成回归 |

T1–T6 已完成实现和直接验收。T6 当时的全量失败保留在历史记录中；后续经 T9 收敛，最终 Windows 全量门禁为 **5713 passed、318 skipped、1 deselected、0 failed**，编译和 wheel/sdist 构建通过。源码包构建与实际产品安装是独立边界。

后续修复：[T7 Windows 路径测试兼容](T7-windows-tests.md)，记录本轮路径误失败的修复及剩余非路径失败。

[T8 平台权限与符号链接能力](T8-platform-test-capabilities.md)：修复权限属性误断言，按实际能力执行符号链接验证。

## 后续验收与兼容审查

- [T9 完整测试门禁](T9-test-gate.md)，提交 `ad143b0`：记录 Windows 测试兼容、用户状态隔离、全部失败/跳过原因和最终构建证据。期间发现的产品缺陷分别由 T9a–T9e 独立方案与提交处理。
- [T10 桌面场景联调](T10-desktop-scenarios.md)，提交 `264a528`：真实开发客户端 IPC/ACP 八场景及六个自动 stdio 回归通过。测试启动配置引发的 `connectors:get-states` 错误已修复，普通开发实例已恢复并重启到最终源码。
- [T11 兼容审查](T11-compatibility-review.md)：前端无需为本轮新增 ACP 字段；SDK 消费模式、严格序列化调用方和自定义委派工具的迁移条件分别列出。前端自身旧测试失败没有计入 Box-Agent 的通过结果。
- [T12 显式工具去重](T12-explicit-tool-deduplication.md)：默认逐次执行，仅可信工具显式允许时批内合并；更新请求快照、Hook 和迁移契约。完整门禁 **5730 passed、318 skipped、1 deselected、0 failed**，编译及 wheel/sdist 构建通过；本项未安装或重启客户端。

当前达到源码、测试、Python 分发包、开发客户端重启/健康探针与确定性场景验证。尚未构建/安装本次 standalone runtime 或正式桌面包，也未在正式包上完成新真实用户任务；下一发布环节沿用原打包流程，必须更新实际携带的 runtime。
