# task26100383

跨校学分认定库：为一名学生、一个目标学校计算严格最优的学分认定方案。
成绩单、课程目录、转学协议通过参数传入，计算数据仅保存在内存。

## 使用说明

    from credit_transfer import (
        evaluate, TranscriptRecord, CourseInfo, AgreementRule,
    )

    transcript = [TranscriptRecord(school_id=1, course_id=10, attempt=1, grade='B')]
    catalog = [CourseInfo(school_id=1, course_id=10, credits=4),
               CourseInfo(school_id=9, course_id=5, credits=3)]
    agreements = [AgreementRule(from_school_id=1, from_course_id=10, to_course_id=5)]

    plan = evaluate(transcript, catalog, agreements, target_school_id=9)
    # plan.assignments    逐项认定结果（可追溯到被采用的修读记录）
    # plan.total_credits  认定总学分
    # plan.total_quality  认定质量分

- 成绩 A/B/C/D/F 对应绩点 4/3/2/1/0，仅 C 及以上可参与认定；
  同一课程多次修读只采用 attempt 序号最大的一次。
- 优化顺序：认定总学分最大 → 认定质量分最大 → 按目标课程编号升序的
  （来源学校编号， 来源课程编号）序列字典序最小（未认定位置视为无穷大）。
  相同内容的输入无论如何排列都得到同一认定关系。

## 运行测试

    python3 -m pytest tests/ -q        # 全部测试
    python3 -m pytest tests/ -q -s     # 含规模测试的耗时与峰值内存报告
## 实现要点

三级优化目标被编码为单个大整数权重（学分 × 10ⁿ 级、质量分次之、字典序位权最低，
各级进制保证低位永远压不过高位），随后用 successive shortest paths 最小费用流
精确求解，因此结果是严格最优而非贪心近似。规模上限（10000 条记录 / 400 来源课程 /
400 目标课程 / 12000 条抵扣关系）下单次计算约 2 秒、峰值内存约 14 MiB。
