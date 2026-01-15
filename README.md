# StoryCrew - AI小说自动生成系统

基于CrewAI的小说自动生成Agent系统，支持都市职场爱情和本格/社会派悬疑两种题材，可生成约27000字（9章×3000字）的完整小说。

## 功能特点

- **8个专业Agent协同工作**：主题规格化、人物设计、结构设计、连续性维护、场景规划、正文撰写、文风编辑、质量评审
- **三幕九章固定结构**：确保故事节奏紧凑，章章有钩子
- **质量门禁机制**：每章通过评审才进入下一章，最多重试2次
- **连续性追踪**：自动维护人物、时间线、线索等事实库
- **双题材支持**：都市职场爱情、本格/社会派悬疑
- **🎯 选择性重试优化**：智能分析质量问题类型，节省 40-60% 重试成本（[详见文档](docs/selective-retry-guide.md)）

## 系统架构

```
初始化阶段 (InitCrew)
    ├─ ThemeInterpreter → StorySpec + StyleGuide
    ├─ ConceptDesigner → 人物 + 关系 + 职场生态/嫌疑人池
    ├─ PlotArchitect → 三幕九章大纲 + 伏笔表
    └─ ContinuityKeeper → StoryBible初始化

章节生成阶段 (ChapterCrew × 9)
    └─ 每章循环：
        ├─ ChapterPlanner → 场景列表(6-10个场景)
        ├─ ChapterWriter → 章节正文(3000±10%字)
        ├─ ContinuityKeeper → 更新StoryBible
        ├─ LineEditor → 文风润色
        └─ CriticJudge → 质量评审(失败则重写)

最终组装阶段 (FinalCrew)
    ├─ CriticJudge → 全书评审(伏笔回收率≥95%)
    └─ AssembleBook → 标题+简介+目录+正文
```

## 选择性重试优化

### 概述

StoryCrew 引入了智能选择性重试机制，根据质量评审中的问题类型，**只重新执行必要的任务**，避免不必要的资源浪费。

### 工作原理

当章节未通过质量评审时，系统会自动分析问题类型并选择最优的重试策略：

| 重试级别 | 适用场景 | 保留内容 | 节省成本 |
|---------|---------|---------|---------|
| **EDIT_ONLY** | 文笔、节奏、字数问题 | SceneList + 草稿 | ~75% |
| **WRITE_ONLY** | 动机、钩子、线索、连续性问题 | SceneList | ~50% |
| **FULL_RETRY** | 结构、严重安全问题 | 无 | 0% |

### 核心优势

- ✅ **成本节省 40-60%**：避免重新规划和撰写不必要的章节
- ✅ **质量保证**：所有质量门禁标准保持不变
- ✅ **完全自动化**：无需手动配置，智能选择重试策略
- ✅ **透明可控**：详细日志记录每次决策过程

### 快速开始

```python
from storycrew.main import run

# 选择性重试默认启用，无需额外配置
result = run(
    genre="romance",
    theme_statement="一个关于职场爱情的故事"
)

# 查看重试统计
if result['success']:
    stats = result['metadata']['retry_stats']
    print(f"EDIT_ONLY: {stats['edit_only']} 次")
    print(f"WRITE_ONLY: {stats['write_only']} 次")
    print(f"FULL_RETRY: {stats['full_retry']} 次")
```

### 详细文档

完整的配置选项、监控方法、故障排除和最佳实践，请参阅：

**[选择性重试优化完整指南](docs/selective-retry-guide.md)**

## 安装

```bash
# 激活虚拟环境
source ~/miniconda3/bin/activate storyCrew

# 安装项目(已安装)
pip install -e .
```

## 使用方法

### 交互式使用（推荐）

直接运行程序，按照提示选择题材和输入主题：

```bash
python -m storycrew.main
```

系统会提示：
1. **选择题材**：输入 1（都市职场爱情）或 2（本格/社会派悬疑）
2. **输入主题**：描述你想写的故事核心（建议100字左右）
3. **输入偏好**（可选）：如特定人物设定、故事风格等

系统会自动生成小说名称，并在 `./novels/小说名称/` 目录下保存所有文件。

### 命令行使用（脚本化）

```bash
# 指定题材和主题（跳过交互）
python -m storycrew.main --genre romance --theme "一个关于职场爱情的故事"

# 生成悬疑小说
python -m storycrew.main --genre mystery --theme "一桩离奇的职场谋杀案"

# 指定基础输出目录
python -m storycrew.main --genre romance --theme "..." --output ./my_novels
```

### Python代码使用

```python
from storycrew.main import run

result = run(
    genre="romance",  # or "mystery"
    theme_statement="一个关于职场爱情的故事",
    additional_preferences="",  # 可选
    output_dir="./novels"  # 基础目录，小说会创建子目录
)

if result['success']:
    print("小说生成成功！")
    print(f"小说名称: {result['novel_name']}")
    print(f"小说目录: {result['novel_dir']}")
```

## 配置说明

### 环境变量 (.env)

```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL_NAME=deepseek-ai/DeepSeek-V3.2
```

### 质量门禁阈值

**章级门禁**：
- `continuity_conflicts == 0` (硬性)
- `character_motivation >= 7`
- `pacing >= 7`
- `hook >= 7`
- `genre_fulfillment >= 7`
- 悬疑额外: `clue_fairness >= 7`

**全书门禁**：
- `plant_payoff_coverage >= 0.95` (伏笔回收率)
- `theme_delivery >= 8`
- `ending_satisfaction >= 8`

## 输出文件

系统会自动生成小说名称，并在 `./novels/小说名称/` 目录下创建所有文件：

```
novels/
└── 小说名称/                 # 系统自动生成的小说名称
    ├── story_spec.json       # 故事规格（包含小说名称）
    ├── story_bible.json      # 初始故事圣经
    ├── story_bible_final.json # 最终故事圣经
    ├── outline.json          # 九章大纲
    ├── chapter_01.md         # 第1章
    ├── chapter_02.md         # 第2章
    ├── ...
    ├── chapter_09.md         # 第9章
    ├── complete_novel.md     # 完整小说（标题+简介+目录+正文）
    ├── final_report.json     # 最终评审报告
    └── generation_metadata.json # 生成元数据（包含小说名称）
```

每本小说都有独立的目录，便于管理和查看。

## 项目结构

```
src/storycrew/
├── models/              # 数据模型(Pydantic)
│   ├── story_spec.py    # StorySpec, StyleGuide
│   ├── story_bible.py   # StoryBible, Character, Clue等
│   ├── outline.py       # ChapterOutline, PlantPayoffTable
│   ├── scene_list.py    # SceneList, Scene
│   └── judge_report.py  # JudgeReport, ScoreBreakdown
├── crews/               # Crew类
│   ├── init_crew.py     # 初始化阶段
│   ├── chapter_crew.py  # 章节生成阶段
│   └── final_crew.py    # 最终组装阶段
├── config/              # 配置文件
│   ├── agents.yaml      # 8个Agent配置
│   └── tasks.yaml       # 12个Task配置
├── crew.py              # 基础Crew配置
└── main.py              # 主入口(编排逻辑)
```

## 设计理念

### 三幕九章结构模板

**第一幕（第1-3章）- 建立与触发**：
- 第1章：日常破裂 + 主角欲望
- 第2章：相遇/案件引爆 + 代价
- 第3章：第一次转折/进入新世界

**第二幕（第4-6章）- 对抗与加深**：
- 第4章：推进与试探
- 第5章：中点反转
- 第6章：代价升级 + 失去

**第三幕（第7-9章）- 崩塌与解决**：
- 第7章：全盘崩塌/最低谷
- 第8章：真相/和解的路径/最终计划
- 第9章：终局兑现主题 + 余韵

### 质量保证机制

1. **字数控制**：每章2700-3300字
2. **连续性检查**：StoryBible追踪所有事实
3. **文风统一**：StyleGuide统一语言风格
4. **节奏优化**：每章必须包含信息增量、情绪增量、章末钩子
5. **伏笔管理**：PlantPayoffTable追踪所有伏笔的埋设和回收

## 扩展题材

要添加新题材，需要修改以下文件：

1. **models/story_spec.py**: 添加题材特定的字段
2. **config/tasks.yaml**: 添加题材特定的prompt
3. **config/agents.yaml**: 可选，调整Agent行为

示例：添加奇幻题材
```python
# models/story_spec.py
class StorySpec(BaseModel):
    # ...
    # 奇幻特定字段
    magic_system: Optional[str] = None
    world_rules: List[str] = Field(default_factory=list)
```

## 已知问题

1. **LLM输出JSON解析**：CrewAI的LLM可能输出不完美的JSON，系统已添加容错机制
2. **重试次数限制**：每章最多重试2次，可能需要人工介入（选择性重试已优化此问题）
3. **生成时间**：9章小说预计需要20-50分钟（取决于LLM速度，选择性重试可节省时间）

## 依赖项

- crewai==1.7.2
- pydantic~=2.11.9
- Python 3.12+

## License

MIT

## 致谢

基于CrewAI框架构建，设计稿来自Crew_Design-GPT.md。
