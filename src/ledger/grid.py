"""Where the electricity came from, decided by you rather than by your IP address.

The default behaviour of a carbon tracker is to geolocate the machine from its
public IP and apply that country's grid factor. Any machine whose traffic leaves
somewhere other than where it sits — behind a corporate proxy, a cloud relay, a
VPN, a university gateway — is assigned the grid of the exit, not its own. The
number comes out plausible, carries a country name, and nobody checks it.

How far off that is depends only on where the exit happens to be. For a machine
drawing power from the Guangdong grid (0.4419 kgCO2/kWh), the factors CodeCarbon
would apply range from 58% too high to sixteen times too low — and even getting
the country right is 32% off, because a national average is not a province.
``IP_GEOLOCATION_EXAMPLES`` holds those figures so the report can show the range
rather than assert it.

So this module does not geolocate. The grid factor is a configured value with a
citation attached, and running without configuring one is an error rather than a
guess.

Factors are the 2023 vintage published by 生态环境部 and 国家统计局 on
2025-12-31, which is the current official set for reporting Chinese electricity
consumption.
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE = {
    "name": "关于发布2023年电力二氧化碳排放因子的公告",
    "issuer": "生态环境部、国家统计局",
    "published": "2025-12-31",
    "url": "https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/202512/W020251231726284332528.pdf",
    "sha256": "d43b60a3eaad9f3fe59ca37c204d3d0e1b6ea52742a092f0d856971a3f018e5a",
}


@dataclass(frozen=True)
class GridFactor:
    region: str
    value: float  # kgCO2 per kWh
    level: str  # national / regional / provincial
    year: int = 2023

    def citation(self) -> str:
        return (
            f"{self.region} {self.year} 年电力平均二氧化碳排放因子 {self.value} kgCO2/kWh"
            f"（{SOURCE['issuer']}，{SOURCE['published']}）"
        )


# The subset needed to report work done in China.  The official table covers
# every province and grid region; these are the ones this tool ships with.
FACTORS = {
    "全国": GridFactor("全国", 0.5306, "national"),
    "南方": GridFactor("南方", 0.4042, "regional"),
    "华东": GridFactor("华东", 0.5500, "regional"),
    "华北": GridFactor("华北", 0.6361, "regional"),
    "广东": GridFactor("广东", 0.4419, "provincial"),
    "北京": GridFactor("北京", 0.5554, "provincial"),
    "上海": GridFactor("上海", 0.5737, "provincial"),
    "浙江": GridFactor("浙江", 0.4974, "provincial"),
    "江苏": GridFactor("江苏", 0.5827, "provincial"),
    "四川": GridFactor("四川", 0.1564, "provincial"),
}

# What an IP-geolocating tracker would apply, by where the traffic exits.
# Taken from CodeCarbon 3.3.1's own country table (data/private_infra/
# global_energy_mix.json, carbon_intensity in g/kWh, divided by 1000), so the
# comparison in the report is its numbers rather than a recollection of them.
IP_GEOLOCATION_SOURCE = "CodeCarbon 3.3.1, global_energy_mix.json"
IP_GEOLOCATION_EXAMPLES = {
    "China (national average)": 0.5823,
    "Hong Kong": 0.6995,
    "Japan": 0.4854,
    "Singapore": 0.4708,
    "South Korea": 0.4306,
    "United States": 0.3695,
    "Iceland": 0.0277,
}


def resolve(region: str) -> GridFactor:
    if region not in FACTORS:
        raise KeyError(
            f"no factor for {region!r}. Available: {', '.join(FACTORS)}. "
            f"Add it from {SOURCE['url']} rather than guessing."
        )
    return FACTORS[region]
