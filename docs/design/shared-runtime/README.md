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

提交前检查目标 diff、暂存 diff 和工作区，使用明确路径暂存。运行时交付止于源码、测试和可构建包；不推送、不安装、不重启产品。

## 评审入口

先读各任务的“修改方案”，再对照提交和“实施与验证”。[SDK 使用及兼容迁移](SDK.md)说明消费模式、错误、权限和终止字段；[T6 验证记录](T6.md)区分直接回归、全量失败和运行时边界。

| 任务 | 提交 | 主要代码 |
| --- | --- | --- |
| T1 | db081ec | run_events、run_result、agent_run |
| T2 | 50b7953 | api/run、api 导出、sdk |
| T3 | e524c97 | agent_run、run_control |
| T4 | cc8df2d | api/delivery、run_events、agent_service、sdk |
| T5 | a6b3320 | tools/delegated_budget、tools/engine、sub_agent_tool |
| T6 | 本记录所在提交 | ACP/Session 取消接点、共享权限等待、SDK 仅结果入口、集成回归 |

T1–T5 已完成实现和直接验收。T6 已实施桌面适配及验证，**全量门禁未通过**，不能视为发布验收完成。源码包构建与实际产品安装是独立边界。

后续修复：[T7 Windows 路径测试兼容](T7-windows-tests.md)，记录本轮路径误失败的修复及剩余非路径失败。

[T8 平台权限与符号链接能力](T8-platform-test-capabilities.md)：修复权限属性误断言，按实际能力执行符号链接验证。
