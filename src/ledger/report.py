"""Render the ledger, keeping measured and estimated runs apart.

Totalling a measured run and an estimated one produces a number that is neither,
so the report groups by method and never adds across the line. Where everything
was estimated it says so in the first sentence, because a reader who takes an
estimate for a measurement has been misled by the format rather than the figures.
"""
from __future__ import annotations

from datetime import date

from .grid import SOURCE
from .measure import Record, counterfactual


def badge_line(records: list[Record]) -> str:
    total_g = sum(r.co2_g for r in records)
    hours = sum(r.duration_s for r in records) / 3600.0
    method = "measured" if all(r.method == "measured" for r in records) else "estimated"
    region = records[-1].region
    factor = records[-1].grid_factor_kg_per_kwh
    return (
        f"Compute for this repository: {hours:.2f} h, {total_g:.1f} g CO2e "
        f"({method}; {region} grid, {factor} kgCO2/kWh, 生态环境部 2023)"
    )


def to_markdown(records: list[Record]) -> str:
    measured = [r for r in records if r.method == "measured"]
    estimated = [r for r in records if r.method == "estimated"]

    lines: list[str] = ["# 计算过程的碳排放台账", ""]
    lines.append(f"> 生成日期：{date.today().isoformat()}")
    lines.append(f"> 记录条数：{len(records)}")
    lines.append("")

    if not measured:
        lines.append(
            "**全部记录为估算，不是实测。** 本机没有以 root 运行 `powermetrics`，"
            "因此功率取的是处理器铭牌值乘以时长。笔记本在任务之间会闲置，"
            "这种估算可能偏高数倍。要得到实测值，用 `sudo` 重跑。"
        )
        lines.append("")

    for name, group in (("实测", measured), ("估算", estimated)):
        if not group:
            continue
        total_kwh = sum(r.energy_kwh for r in group)
        total_g = sum(r.co2_g for r in group)
        hours = sum(r.duration_s for r in group) / 3600.0
        lines.append(f"## {name}（{len(group)} 条）")
        lines.append("")
        lines.append(
            f"合计 {hours:.2f} 小时，{total_kwh * 1000:.1f} Wh，{total_g:.1f} g CO2e。"
        )
        lines.append("")
        lines.append("| 项目 | 任务 | 时长 | 电量 | 排放 | 电网 |")
        lines.append("|---|---|---|---|---|---|")
        for r in sorted(group, key=lambda x: -x.duration_s):
            lines.append(
                f"| {r.project} | {r.label} | {r.duration_s:.0f} s | "
                f"{r.energy_kwh * 1000:.2f} Wh | {r.co2_g:.2f} g | "
                f"{r.region} {r.grid_factor_kg_per_kwh} |"
            )
        lines.append("")

    if records:
        sample = max(records, key=lambda r: r.energy_kwh)
        rows = counterfactual(sample)
        lines.append("## 如果不指定电网区域会怎样")
        lines.append("")
        lines.append(
            f"按 IP 定位的追踪器会用公网出口所在国家的因子，而出口在哪取决于网络路由，"
            f"不取决于机器在哪。下表把耗电最多的一条记录"
            f"（{sample.label}，{sample.energy_kwh * 1000:.2f} Wh）"
            f"按不同出口重新计算，对照按{sample.region}电网"
            f"（{sample.grid_factor_kg_per_kwh} kgCO2/kWh）得到的 {sample.co2_g:.2f} g："
        )
        lines.append("")
        lines.append("| 公网出口解析到 | 套用的因子 | 算出的排放 | 相对误差 |")
        lines.append("|---|---|---|---|")
        for row in sorted(rows, key=lambda r: -r["factor"]):
            lines.append(
                f"| {row['exit']} | {row['factor']} | {row['co2_kg'] * 1000:.2f} g | "
                f"{row['error_pct']:+.0f}% |"
            )
        lines.append("")
        lines.append(
            f"因子取自 {rows[0]['source']}。同一台机器、同一段计算，"
            "只因为出口不同，结果可以从高估一半以上到低估到十六分之一，而输出看上去毫无异常。"
            "即便国家判对了，全国平均也不是一个省。所以本工具不做地理定位，电网区域必须显式指定。"
        )
        lines.append("")

    lines.append("## 口径")
    lines.append("")
    lines.append(f"- 排放因子：{SOURCE['issuer']}，{SOURCE['name']}，{SOURCE['published']}")
    lines.append(f"- 原文：{SOURCE['url']}")
    lines.append(f"- 源文件 SHA-256：`{SOURCE['sha256']}`")
    lines.append(
        "- 电量由 CodeCarbon 采集；本工具只负责把电网因子钉死、"
        "标注实测还是估算、并保留原始千瓦时以便日后更正无需重跑。"
    )
    lines.append(
        "- 只计本机计算，不含模型训练之外的任何环节，也不含制造与网络传输。"
    )
    return "\n".join(lines)
