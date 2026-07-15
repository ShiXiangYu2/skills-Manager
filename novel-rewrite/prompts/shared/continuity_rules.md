# 连续性硬规则

## 进入本章前的连续性状态快照

制定任何方案前，必须先从前文摘要中提取进入本章时的硬状态：

```json
"state_snapshot": {
  "characters": [
    {
      "name": "角色名",
      "physical_state": "身体状态、伤势、疲劳、能力限制",
      "mental_state": "心理状态、情绪压力、认知误区",
      "relationship_state": "与关键角色的关系状态",
      "knowledge_state": "此时知道/不知道的信息",
      "capability_limits": "本章开始时不能轻易突破的能力限制"
    }
  ],
  "active_injuries_or_constraints": [],
  "unresolved_threads": [],
  "forbidden_contradictions": []
}
```

## 硬性要求

- 如果前文显示某角色虚弱、受伤、昏迷、失控、能力受限，本章必须显式延续
- 如果需要让状态恢复，必须给出恢复原因、时间消耗或代价
- 不允许把前章重大状态当作已经自动消失
- 受伤角色不能突然高强度动作，除非文本明确写出代价
- 虚弱角色不能长时间稳定对话，除非有合理恢复机制
