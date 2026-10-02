# 跨校学分认定库（credit_transfer）

纯 Python、零依赖的学分认定库。成绩单、课程目录和转学协议通过参数传入，
计算数据仅保存在内存，每次调用为一名学生、一个目标学校产出完整认定方案。

## 快速开始

```python
from credit_transfer import (
    Agreement, CourseInfo, TranscriptRecord, compute_plan,
)

plan = compute_plan(
    target_school_id=2,
    transcript=[TranscriptRecord(school_id=1, course_id=101, attempt=1, grade="A")],
    catalog=[CourseInfo(1, 101, 4), CourseInfo(2, 201, 3)],
    agreements=[Agreement(1, 101, 2, 201)],
)

print(plan.total_credits)    # 认定总学分：3
print(plan.quality_points)   # 认定质量分：3 * 4 = 12
for item in plan.items:      # 按目标课程编号升序，可追溯到修读记录
    print(item.target_course_id, "<-", item.source_school_id, item.source_course_id,
          "attempt", item.attempt, item.grade)
```

## 输入模型

- `TranscriptRecord(school_id, course_id, attempt, grade)`：一条修读记录。
  `attempt` 为该课程内唯一的修读序号；同一课程多次修读只采用序号最大
  的一次，最近一次不及格（C 以下）则整门课程失去转入资格。
  成绩为 `A/B/C/D/F`，对应绩点 `4/3/2/1/0`。
- `CourseInfo(school_id, course_id, credits)`：课程目录，学分 1 至 4。
  成绩单与协议中出现的课程都必须在目录中。
- `Agreement(source_school_id, source_course_id, target_school_id,
  target_course_id)`：一条直接抵扣关系。只采用目标学校为本次计算
  目标学校的协议；关系不反向、不沿第三所学校传递。
- 学校编号、课程编号、修读序号均为正整数；不同学校的同号课程互不相关。

## 认定规则

- 来源课程学分不得少于目标课程学分；认定学分等于目标课程学分，
  多出的来源学分作废；不能拼接多门来源课程。
- 每门来源课程最多抵扣一门目标课程，每门目标课程最多被抵扣一次。
- 在全部合法方案中依次优化：认定总学分最大 → 认定质量分
  （各项目标学分 × 来源绩点之和）最大 → 按目标课程编号升序逐项比较
  （来源学校编号， 来源课程编号）的序列字典序最小（未认定视为最大）。
  因此相同内容的输入无论如何排列都得到同一认定关系。

## 输出

`RecognitionPlan`：`items` 为逐项认定结果（含目标/来源课程、学分、
被采用修读记录的序号、成绩与绩点），`total_credits` 与
`quality_points` 为两项总数；无可认定课程时两者均为 0。

## 算法

最小费用流求（总学分， 质量分）两级最优，再基于零约化费用残量环
逐目标课程确定字典序最小来源，严格最优，非近似。规模上限
（10000 修读记录、400 来源课程、400 目标课程、12000 抵扣关系）下
单次计算约 2 秒、峰值内存约 4 MiB。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

覆盖：连续改派多个抵扣关系才能最优的链式案例、先得 A 后得 F 与恰好
为 C 的成绩规则、小规模随机实例与独立穷举的完整方案对拍（含质量分
与同分选择）、输入重排不变性，以及上述规模的性能测试（报告耗时与
峰值内存）。
