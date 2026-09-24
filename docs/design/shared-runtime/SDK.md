# 共享 Run 接口与迁移

宿主拥有 Session 的创建和清理；桌面保持独立 Agent 和第三方模型能力。以下调用均使用现有 Session。

## 只取结果

```python
from box_agent.api import RunRequest, RunDeliveryOptions
from box_agent.sdk import AgentClient

client = AgentClient(session)
result = await client.run(
    RunRequest("run-1", "session-1", "执行任务"),
    delivery_options=RunDeliveryOptions(),
)
```

`run()` 使用仅结果模式并返回 `RunResult`；执行/交付失败通过 `status="failed"` 和 `error` 返回。`start()` 返回 handle 后直接等待 `result()` 也选择此模式。内部消费者持续排空事件，不保留供稍后重放的副本。

## 流式消费

```python
handle = await client.start(RunRequest("run-2", "session-1", "执行任务"))
async with handle:
    async for envelope in handle.events():
        await render(envelope.payload)
    result = await handle.result()
```

首次实际迭代 `events()` 登记唯一流式消费者。登记后可并发等待 `result()`，它不会抢走事件；重复订阅报错。若 `result()` 先登记，仅结果模式不可切回流式。只创建异步生成器对象不算登记。

取消单个 `handle.result()` 等待者不取消运行；显式使用 `cancel()` 或 `aclose()` 结束运行。提前退出流式消费应关闭迭代器或使用 handle 的上下文管理器。

## 终止与错误

`status` 和 `stop_reason` 保留旧映射。新增只读派生字段 `termination_kind` 随 `to_dict()` 输出：

| stop_reason | termination_kind |
| --- | --- |
| end_turn | normal |
| max_steps、max_tokens | budget_exhausted |
| interrupted | interrupted |
| cancelled | cancelled |
| waiting_for_user | waiting_for_user |
| error | failed |
| 未知原因 | unknown |

`COMPLETED` 或 `normal` 只代表该回合结束，不证明用户目标已经验收。宿主需要自己的目标验收逻辑。

流式交付失败会在 `events()` 抛出 `RunDeliveryError` 子类，同时结果中保留结构化错误；仅结果模式检查 `result.error`。稳定错误码：`RUN_EVENT_TOO_LARGE`、`RUN_EVENT_CONSUMER_TIMEOUT`、`RUN_EVENT_DELIVERY_FAILED`。ACP 保留现有线协议，交付异常进入现有请求错误路径。

## 容量与权限

`RunDeliveryOptions` 默认 `max_events=1024`、`max_bytes=4194304`、`congestion_timeout_seconds=30`。统计完整事件 envelope 的紧凑 JSON UTF-8 大小，包括编号字段；每个入队事件计算一次。两项积压均降到 50% 且待写事件可放入时恢复。上限只覆盖通道积压，不是进程总内存上限；序列化临时对象、模型内部缓冲和结果聚合另外占用内存。

超大事件立即失败，不自动裁剪工具结果。调用方可通过宿主交付选项提高额度，或使用已有工具结果引用机制。参数不进入 ACP 协议或用户配置文件。

使用 `PermissionBroker` 时，流式消费者通过 `handle.send(ControlCommand.permission_response(...))` 回复。仅结果模式调用配置的 `on_request`，回调必须在返回前回复请求，可以异步等待宿主；没有回复即拒绝。普通宿主 negotiator 的等待也受共享 Run 取消控制。ACP 继续使用现有权限反向 RPC。

## 委派硬预算

配置 `max_delegated_tool_calls` 后，内置子 Agent 的工具执行共享祖先账本。该限额独立于父级直接调用和子任务自身额度。已进入执行的失败/取消不退款，权限请求等明确未执行尝试释放扣费。完成回报只作统计。

自定义同名 `sub_agent` 必须支持调用上下文、声明 `supports_delegated_budget=True`，并在子作用域绑定 `context.child_budgets`、使用共享工具调用入口。声明属于可信插件契约，不是安全隔离；未接入的实现会被明确拒绝。未配置父级委派限制时保留旧行为。
