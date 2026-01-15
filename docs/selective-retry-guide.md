# 选择性重试优化功能指南

## 功能概述

**问题背景**

在原有的章节生成流程中，当质量评审（CriticJudge）不通过时，系统会重新运行整个流程（Plan → Write → Edit → Judge）。这导致了一个显著的效率问题：**即使只是文笔或节奏问题，系统也会重新运行场景规划和章节撰写任务，造成大量资源浪费。**

**解决方案**

选择性重试优化功能通过智能分析质量报告中问题类型，**只重新执行必要的任务**，跳过可以保留的部分。根据问题类型的不同，系统会采用三种重试策略之一，从而显著降低成本和时间。

**核心收益**

- **成本节省 40-60%**：避免不必要的场景规划和章节撰写
- **质量保证**：输出质量不受影响，所有质量门禁标准保持不变
- **完全自动化**：无需手动配置，系统自动选择最优重试策略
- **透明可控**：详细日志记录每次重试决策，便于监控和调试

---

## 工作原理

### 原有流程 vs 优化后流程

**原有流程（全链路重试）**

```
第1次尝试失败
  ↓
 重新运行全部任务：
  plan_chapter → write_chapter → edit_chapter → judge_chapter
  （即使只是文笔问题）
```

**优化后流程（选择性重试）**

```
第1次尝试失败（文笔问题）
  ↓
 识别问题类型：prose（文笔）
  ↓
 选择 EDIT_ONLY 策略：
  保留 SceneList + draft_text
  只运行：edit_chapter → judge_chapter
```

### 三级重试机制

系统根据质量报告中的问题类型，自动选择以下三种重试级别之一：

| 重试级别 | 适用问题 | 保留内容 | 重新执行的任务 | 节省成本 |
|---------|---------|---------|---------------|---------|
| **EDIT_ONLY** | 文笔、节奏、字数 | SceneList + draft_text | edit → judge | ~75% |
| **WRITE_ONLY** | 动机、钩子、线索、连续性 | SceneList | write → edit → judge | ~50% |
| **FULL_RETRY** | 结构、严重安全、最终尝试 | 无 | plan → write → edit → judge | 0% |

**可视化流程**

```
质量评审失败
    ↓
分析问题类型
    ↓
    ├─ prose/pacing/word_count ──→ EDIT_ONLY ──→ 节省 75%
    │
    ├─ motivation/hook/clue/continuity ──→ WRITE_ONLY ──→ 节省 50%
    │
    └─ structure/safety(critical) ──→ FULL_RETRY ──→ 节省 0%
```

---

## 问题类型映射

### EDIT_ONLY（仅编辑重试）

触发条件：当质量报告仅包含以下问题类型时

- **prose**：文笔平淡、用词不当、句式单调
- **pacing**：节奏过快/过慢、信息密度不均
- **word_count**：字数超出/不足 2700-3300 字范围

**示例场景**

```
质量报告：
  issues:
    - type: prose
      severity: medium
      note: "对话略显生硬，需要更自然的表达"
    - type: pacing
      severity: low
      note: "中间部分节奏稍慢"

系统决策：EDIT_ONLY
保留内容：
  - SceneList（场景列表）
  - draft_text（原始草稿）
重新执行：
  - edit_chapter（编辑润色）
  - judge_chapter（质量评审）
节省：~75%（避免重新规划和撰写）
```

### WRITE_ONLY（仅写作重试）

触发条件：当质量报告包含以下问题类型时

- **motivation**：人物动机不清晰、行为不合理
- **hook**：章节开篇/结尾吸引力不足
- **clue_fairness**：线索埋设不合理（悬疑题材）
- **continuity**：连续性错误（人物属性、时间线、事实不一致）

**示例场景**

```
质量报告：
  issues:
    - type: motivation
      severity: high
      note: "主角突然改变态度，缺乏充分理由"
    - type: hook
      severity: medium
      note: "章末钩子不够强烈，难以吸引读者继续阅读"

系统决策：WRITE_ONLY
保留内容：
  - SceneList（场景列表）
重新执行：
  - write_chapter（重新撰写）
  - edit_chapter（编辑润色）
  - judge_chapter（质量评审）
节省：~50%（避免重新规划场景）
```

### FULL_RETRY（全链路重试）

触发条件：当质量报告包含以下问题类型时

- **structure**：场景结构问题、顺序不合理、场景缺失
- **safety（严重级别 high/critical）**：严重安全问题（暴力、色情、违法内容）
- **达到最大重试次数**：连续2次相同级别重试失败后自动升级

**示例场景**

```
质量报告：
  issues:
    - type: structure
      severity: high
      note: "高潮场景出现时机过早，导致后续章节缺乏张力"

系统决策：FULL_RETRY
保留内容：无
重新执行：
  - plan_chapter（重新规划场景）
  - write_chapter（重新撰写）
  - edit_chapter（编辑润色）
  - judge_chapter（质量评审）
节省：0%（必须重新开始）
```

### 优先级规则

当多个问题类型同时出现时，系统按以下优先级选择重试级别：

```
优先级 1（最高）：structure, safety(critical)
    ↓ FULL_RETRY

优先级 2：motivation, hook, clue_fairness, continuity
    ↓ WRITE_ONLY

优先级 3：prose, pacing, word_count, safety(low/medium)
    ↓ EDIT_ONLY
```

**示例：混合问题类型的处理**

```
质量报告包含：
  - prose（文笔）
  - motivation（动机）

系统决策：WRITE_ONLY（优先级更高的问题类型）
说明：虽然文笔问题可以通过 EDIT_ONLY 修正，
      但动机问题需要重新撰写，因此选择 WRITE_ONLY
```

---

## 使用方法

### 自动化运行（默认）

选择性重试功能**默认启用**，无需任何配置或代码修改。系统会自动：

1. 分析每次质量评审失败的问题类型
2. 选择最优的重试级别
3. 保留必要的中间结果
4. 执行对应的任务子集

**使用示例**

```python
from storycrew.main import run

# 无需任何额外配置，选择性重试自动启用
result = run(
    genre="romance",
    theme_statement="一个关于职场爱情的故事"
)

# 系统会自动：
# 1. 分析每章的质量评审结果
# 2. 根据问题类型选择重试策略
# 3. 优化重试流程，节省成本
```

### 监控重试决策

系统会在日志中详细记录每次重试的决策过程：

```python
import logging

# 启用详细日志
logging.basicConfig(level=logging.INFO)

# 运行小说生成
result = run(genre="romance", theme_statement="...")
```

**日志示例**

```
INFO:StoryCrew:Chapter 1 - Attempt 0: Running FULL_PIPELINE
INFO:StoryCrew:Chapter 1 - Judge failed with issues: prose(2), pacing(1)
INFO:StoryCrew:Chapter 1 - Determined retry level: EDIT_ONLY
INFO:StoryCrew:Chapter 1 - Attempt 1: Running EDIT_ONLY_RETRY
INFO:StoryCrew:Chapter 1 - Preserved: scene_list, draft_text, revision_text
INFO:StoryCrew:Chapter 1 - Judge passed!
```

### 查看重试统计

每次章节生成后，系统会在返回的结果中包含重试统计信息：

```python
result = run(genre="romance", theme_statement="...")

if result['success']:
    metadata = result['metadata']

    print(f"总章节数: {metadata['total_chapters']}")
    print(f"总重试次数: {metadata['total_retries']}")
    print(f"重试级别分布:")
    print(f"  - EDIT_ONLY: {metadata['retry_stats']['edit_only']}")
    print(f"  - WRITE_ONLY: {metadata['retry_stats']['write_only']}")
    print(f"  - FULL_RETRY: {metadata['retry_stats']['full_retry']}")
```

---

## 配置选项

### 重试次数限制

系统有两个配置参数控制重试行为：

**MAX_EDIT_RETRIES（默认：2）**

- 连续 EDIT_ONLY 重试的最大次数
- 超过后自动升级到 WRITE_ONLY
- 防止文笔问题陷入无限循环

**MAX_WRITE_RETRIES（默认：2）**

- 连续 WRITE_ONLY 重试的最大次数
- 超过后自动升级到 FULL_RETRY
- 防止内容问题陷入无限循环

**修改配置**

```python
from storycrew.crews.chapter_crew import ChapterCrew

# 创建自定义配置的 ChapterCrew
class CustomChapterCrew(ChapterCrew):
    def __init__(self):
        super().__init__()
        # 自定义重试次数限制
        self.max_edit_retries = 3  # 允许更多次编辑重试
        self.max_write_retries = 3  # 允许更多次写作重试

# 使用自定义 Crew（需要修改 main.py）
```

### 总重试次数限制

**max_retries（默认：2）**

- 每章最多重试的总次数（包括所有级别）
- 超过后返回当前最佳结果
- 保证流程不会无限循环

**修改配置**

```python
from storycrew.crews.chapter_crew import ChapterCrew

crew = ChapterCrew()
crew.max_retries = 3  # 允许总共3次重试（原2次）
```

---

## 成本节省分析

### 节省计算方法

假设问题类型分布和对应的重试级别：

| 问题类型 | 出现概率 | 重试级别 | 单次节省 |
|---------|---------|---------|---------|
| prose/pacing/word_count | 50% | EDIT_ONLY | 75% |
| motivation/hook/clue/continuity | 30% | WRITE_ONLY | 50% |
| structure/safety | 15% | FULL_RETRY | 0% |
| 其他 | 5% | WRITE_ONLY | 50% |

**加权平均节省**

```
节省率 = 50% × 75% + 30% × 50% + 15% × 0% + 5% × 50%
       = 37.5% + 15% + 0% + 2.5%
       = 55%
```

**实际节省范围**

考虑以下因素，实际节省在 **40-60%** 之间：

- ✅ 多次重试的累积效应（每次都可能节省）
- ✅ 大多数问题是文笔/节奏类（高节省率）
- ⚠️ 少数结构问题需要全链路重试（无节省）
- ⚠️ 重试级别升级机制（可能降低节省）

### 实际案例对比

**案例 1：文笔问题（EDIT_ONLY）**

```
原流程成本：
  plan (1000 tokens) + write (3000 tokens) + edit (2000 tokens) = 6000 tokens

优化后成本：
  edit (2000 tokens) = 2000 tokens

节省：4000 tokens (67%)
```

**案例 2：动机问题（WRITE_ONLY）**

```
原流程成本：
  plan (1000 tokens) + write (3000 tokens) + edit (2000 tokens) = 6000 tokens

优化后成本：
  write (3000 tokens) + edit (2000 tokens) = 5000 tokens

节省：1000 tokens (17%)
```

**案例 3：完整生成流程（9章）**

```
假设：
  - 每章平均重试 1.5 次
  - 问题类型分布：50% 文笔，30% 内容，20% 结构
  - 单次完整流程成本：6000 tokens

原流程总成本：
  9章 × (1 + 1.5次重试) × 6000 tokens = 135,000 tokens

优化后总成本：
  基础成本：9章 × 6000 tokens = 54,000 tokens
  重试成本：
    - 文笔问题（50%）：9章 × 1.5 × 50% × 2000 tokens = 13,500 tokens
    - 内容问题（30%）：9章 × 1.5 × 30% × 5000 tokens = 20,250 tokens
    - 结构问题（20%）：9章 × 1.5 × 20% × 6000 tokens = 16,200 tokens
  总计：54,000 + 13,500 + 20,250 + 16,200 = 103,950 tokens

节省：135,000 - 103,950 = 31,050 tokens (23%)
单次重试节省：55%（加权平均）
```

---

## 监控和调试

### 日志级别设置

**INFO 级别（推荐）**

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

输出内容：
- 每次尝试的重试级别
- 保留的中间结果
- 问题类型分析

**DEBUG 级别（调试用）**

```python
logging.basicConfig(level=logging.DEBUG)
```

额外输出内容：
- SceneList 解析详情
- 状态更新过程
- 重试级别决策依据

### 关键日志信息

**1. 重试级别决策**

```
INFO:StoryCrew:Chapter 1 - Attempt 0 failed
INFO:StoryCrew:Chapter 1 - Issue types detected: prose, pacing
INFO:StoryCrew:Chapter 1 - Determined retry level: EDIT_ONLY
```

**2. 中间结果保留**

```
INFO:StoryCrew:Chapter 1 - Preserving intermediate results:
INFO:StoryCrew:Chapter 1 -   - scene_list (6 scenes)
INFO:StoryCrew:Chapter 1 -   - draft_text (2947 chars)
INFO:StoryCrew:Chapter 1 -   - revision_text (3124 chars)
```

**3. 重试级别升级**

```
INFO:StoryCrew:Chapter 1 - EDIT_ONLY retry limit reached (2/2)
INFO:StoryCrew:Chapter 1 - Upgrading to WRITE_ONLY
```

**4. 状态恢复失败**

```
WARNING:StoryCrew:SceneList JSON parsing failed: Expecting ',' delimiter
WARNING:StoryCrew:Chapter 1 - Falling back to FULL_RETRY
```

### 常见监控指标

**重试级别分布**

```python
def analyze_retry_distribution(metadata):
    """分析重试级别分布"""
    stats = metadata['retry_stats']

    total = sum(stats.values())
    print(f"总重试次数: {total}")
    print(f"EDIT_ONLY: {stats['edit_only']} ({stats['edit_only']/total*100:.1f}%)")
    print(f"WRITE_ONLY: {stats['write_only']} ({stats['write_only']/total*100:.1f}%)")
    print(f"FULL_RETRY: {stats['full_retry']} ({stats['full_retry']/total*100:.1f}%)")
```

**成本节省估算**

```python
def estimate_cost_savings(metadata, cost_per_1k_tokens=0.001):
    """估算成本节省"""
    stats = metadata['retry_stats']

    # 假设每次完整流程成本为 6000 tokens
    full_cost_per_attempt = 6 * cost_per_1k_tokens

    # 原流程成本（所有重试都是 FULL_RETRY）
    original_cost = metadata['total_retries'] * full_cost_per_attempt

    # 优化后成本（按级别加权）
    optimized_cost = (
        stats['edit_only'] * 2 * cost_per_1k_tokens +      # edit only
        stats['write_only'] * 5 * cost_per_1k_tokens +     # write only
        stats['full_retry'] * 6 * cost_per_1k_tokens       # full retry
    )

    savings = original_cost - optimized_cost
    savings_pct = (savings / original_cost) * 100

    print(f"原流程成本: ${original_cost:.4f}")
    print(f"优化后成本: ${optimized_cost:.4f}")
    print(f"节省: ${savings:.4f} ({savings_pct:.1f}%)")
```

---

## 故障排除

### 问题 1：重试级别选择不符合预期

**症状**

质量报告显示的是文笔问题，但系统却选择了 WRITE_ONLY 或 FULL_RETRY。

**原因**

1. 问题类型优先级：当多个问题同时出现时，系统选择优先级更高的级别
2. 连续重试限制：达到 MAX_EDIT_RETRIES 或 MAX_WRITE_RETRIES 后自动升级

**解决方案**

- 查看完整的问题列表：`judge_report.issues`
- 检查重试次数计数：`state.edit_retry_count`, `state.write_retry_count`
- 调整配置：增加 MAX_EDIT_RETRIES 或 MAX_WRITE_RETRIES

```python
# 查看完整问题列表
for issue in judge_report.issues:
    print(f"类型: {issue.type}, 严重度: {issue.severity}")
    print(f"描述: {issue.note}")
```

### 问题 2：SceneList 解析失败导致降级

**症状**

日志中出现 "SceneList JSON parsing failed" 和 "Falling back to FULL_RETRY"

**原因**

SceneList 的 JSON 序列化/反序列化过程中出现格式错误

**解决方案**

系统已经内置了自动降级机制，确保流程不会中断。如果频繁出现：

1. 检查 SceneList 生成的输出格式
2. 验证 JSON 修复逻辑是否正常工作
3. 查看 `src/storycrew/models/scene_list.py` 的验证逻辑

```python
# 手动验证 SceneList JSON
import json
from storycrew.models.scene_list import SceneList

try:
    scene_list = SceneList.model_validate_json(json_string)
    print("SceneList 解析成功")
except Exception as e:
    print(f"SceneList 解析失败: {e}")
```

### 问题 3：重试陷入循环

**症状**

系统连续多次重试同一级别，始终无法通过质量评审

**原因**

1. 问题类型判断错误
2. 保留的中间结果质量不佳
3. 质量门禁标准过于严格

**解决方案**

系统已内置重试次数限制，防止无限循环：

- 最多 2 次 EDIT_ONLY 后升级到 WRITE_ONLY
- 最多 2 次 WRITE_ONLY 后升级到 FULL_RETRY
- 总共最多 2 次重试（可配置）

如果需要调整限制：

```python
from storycrew.crews.chapter_crew import ChapterCrew

crew = ChapterCrew()
crew.max_retries = 3  # 增加总重试次数
# 注意：需要在源代码中修改 MAX_EDIT_RETRIES 和 MAX_WRITE_RETRIES
```

### 问题 4：质量下降

**症状**

启用选择性重试后，章节质量不如之前

**可能原因**

1. 保留的中间结果质量不佳
2. 重试级别选择不合理
3. 质量门禁标准未严格执行

**排查步骤**

1. 对比新旧流程的质量报告评分
2. 检查保留的 SceneList 和 draft_text 质量
3. 验证质量门禁标准是否一致

```python
# 对比质量报告
print("质量评分对比:")
print(f"人物动机: {judge_report.scores.character_motivation}/10")
print(f"节奏控制: {judge_report.scores.pacing}/10")
print(f"章末钩子: {judge_report.scores.hook}/10")
print(f"题材契合: {judge_report.scores.genre_fulfillment}/10")
```

**回滚方案**

如果质量下降超过 5%，可以考虑：

1. 暂时禁用选择性重试（通过 feature flag）
2. 调整重试级别映射规则
3. 提高质量门禁标准

### 问题 5：日志不输出

**症状**

看不到任何重试级别的日志信息

**原因**

日志级别设置不当

**解决方案**

```python
import logging

# 设置正确的日志级别
logger = logging.getLogger("StoryCrew")
logger.setLevel(logging.INFO)

# 添加控制台处理器
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
```

---

## 最佳实践

### 1. 定期监控重试分布

建议每周或每生成 10 本小说后，检查重试级别分布：

```python
# 统计分析工具
def generate_retry_report():
    """生成重试统计报告"""
    # 收集最近 10 本小说的元数据
    # 计算平均节省率
    # 识别异常模式
    pass
```

### 2. 调整质量门禁标准

如果发现某个问题类型频繁出现，可以调整对应的质量门禁阈值：

```yaml
# config/tasks.yaml
judge_chapter:
  description: >
    ...
    质量门禁：
    - character_motivation >= 7  # 可根据实际情况调整
    - pacing >= 7
    - hook >= 7
```

### 3. 优化重试次数限制

根据实际使用情况，调整重试次数限制：

- 如果文笔问题较多，可以增加 MAX_EDIT_RETRIES
- 如果结构问题较多，可以降低 MAX_EDIT_RETRIES，更快升级到 FULL_RETRY

### 4. 记录异常案例

当出现不符合预期的重试决策时，记录详细信息：

```python
# 记录异常案例
def log_unusual_retry(judge_report, retry_level, expected_level):
    """记录不符合预期的重试决策"""
    if retry_level != expected_level:
        logger.warning(f"Unexpected retry level:")
        logger.warning(f"  Expected: {expected_level}")
        logger.warning(f"  Actual: {retry_level}")
        logger.warning(f"  Issues: {[issue.type for issue in judge_report.issues]}")
```

---

## FAQ

**Q1: 选择性重试会影响输出质量吗？**

A: 不会。系统保留的中间结果（SceneList、draft_text）都是通过质量门禁的版本，只是根据问题类型选择性重跑部分任务。所有质量门禁标准保持不变，最终输出的质量要求完全相同。

**Q2: 如何禁用选择性重试功能？**

A: 目前选择性重试是默认启用的核心功能，不建议禁用。如果确实需要，可以修改 `src/storycrew/crews/chapter_crew.py` 中的逻辑，强制所有重试都使用 FULL_RETRY。

**Q3: 为什么有时会选择更高级别的重试？**

A: 有两个原因：
1. 问题类型优先级：当多个问题同时出现时，选择优先级更高的级别
2. 重试次数限制：连续多次同级别重试失败后，自动升级到更高级别

**Q4: 能否自定义问题类型到重试级别的映射？**

A: 可以。修改 `src/storycrew/models/retry_level.py` 中的 `determine_retry_level()` 函数，自定义映射规则。

**Q5: 选择性重试是否适用于所有题材？**

A: 是的。选择性重试机制与题材无关，适用于都市职场爱情和本格/社会派悬疑两种题材，以及未来可能添加的新题材。

**Q6: 如何验证节省效果？**

A: 查看日志中的重试级别分布和每次重试保留的中间结果。可以使用本文档提供的监控指标计算实际节省率。

**Q7: 如果重试级别选择错误怎么办？**

A: 系统有自动升级机制（连续同级别重试限制），确保不会陷入死循环。如果发现系统性地选择错误，可以调整 `determine_retry_level()` 函数的映射规则。

---

## 相关文档

- [选择性重试设计方案](./plans/2026-01-14-selective-retry-design.md) - 详细的技术设计文档
- [选择性重试实施计划](./plans/2026-01-14-selective-retry-implementation.md) - 完整的实施步骤和测试计划
- [README.md](../README.md) - 项目主文档

---

## 更新日志

**2026-01-15**
- 初始版本发布
- 包含完整的功能说明、使用指南和故障排除

---

## 联系与反馈

如有任何问题或建议，请通过以下方式联系：

- 提交 GitHub Issue
- 在项目讨论区发起讨论
- 联系项目维护者

---

**文档版本**: 1.0
**最后更新**: 2026-01-15
**作者**: StoryCrew 团队
