# green-ai-ledger

Measure what your compute costs in carbon, with the grid factor **pinned to a
cited source** instead of guessed from your IP address.

```bash
ledger run --label "train the model" --project my-repo -- make train
ledger report --out reports/green-ai.md
```

## Why this exists

Run a carbon tracker out of the box and it geolocates your machine from its
public IP, then applies that country's grid factor. But a public IP says where
the traffic leaves, not where the machine is. Behind a corporate proxy, a cloud
relay, a VPN or a university gateway, the tracker applies the grid of the exit —
and the number comes out plausible, carries a country name, and nobody re-checks
it.

How wrong depends only on where the exit happens to be. Here is the heaviest job
in this ledger, 2.29 Wh on a machine drawing from the Guangdong grid, re-scored
with the factor CodeCarbon 3.3.1 would apply for each exit country:

| Public IP resolves to | Factor applied | Result | Error |
|---|---|---|---|
| **Guangdong grid (correct)** | **0.4419** | **1.01 g** | — |
| Hong Kong | 0.6995 | 1.60 g | +58% |
| China, national average | 0.5823 | 1.33 g | +32% |
| Japan | 0.4854 | 1.11 g | +10% |
| South Korea | 0.4306 | 0.98 g | −3% |
| United States | 0.3695 | 0.84 g | −16% |
| Iceland | 0.0277 | 0.06 g | −94% |

Same machine, same work: anything from half again too much to a sixteenth of
the right answer, depending on a routing detail nobody reports. And the second
row is the quieter point — **even getting the country right is 32% off**,
because a national average is not a province.

So this tool refuses to geolocate. The region is an argument, an unknown region
is an error rather than a fallback, and every factor carries its issuing body,
document, URL, publication date and the SHA-256 of the source file.

```bash
$ ledger factors
  全国     0.5306   kgCO2/kWh  [national]
  南方     0.4042   kgCO2/kWh  [regional]
  广东     0.4419   kgCO2/kWh  [provincial]
  四川     0.1564   kgCO2/kWh  [provincial]
  ...
生态环境部、国家统计局，关于发布2023年电力二氧化碳排放因子的公告，2025-12-31
sha256 d43b60a3eaad9f3fe59ca37c204d3d0e1b6ea52742a092f0d856971a3f018e5a
```

The spread within one country makes the same point from the other side: 0.1564
in Sichuan against 0.6361 in the north, a factor of four. "Which country" is not
a fine enough question.

## Measured is not the same as estimated

macOS exposes real per-subsystem power through `powermetrics`, which needs root.
Without root, every tool — this one included — falls back to the processor's
nameplate wattage multiplied by elapsed time. That is an assumption about
average utilisation wearing the clothes of a measurement, and on a laptop that
idles between bursts it can be out by several times.

So every record carries a `method` field, the report totals the two groups
separately and never adds across the line, and a ledger of estimates says so in
its first sentence:

> **全部记录为估算，不是实测。** 本机没有以 root 运行 `powermetrics`，因此功率取的
> 是处理器铭牌值乘以时长。笔记本在任务之间会闲置，这种估算可能偏高数倍。

The raw kilowatt-hours are kept in the ledger alongside the factor, so if either
turns out to be wrong the figure can be recomputed without re-running the work.

The ledger is meant to be committed next to the work it measures, so the command
line it records has the home directory written as `~` — an interpreter's
absolute path otherwise carries the user's name into a public file.

## What it measured

Three runs across two of my repositories
([pv-wind-power-forecast](https://github.com/Zhaohh0706/pv-wind-power-forecast),
[aiwp-china-verification](https://github.com/Zhaohh0706/aiwp-china-verification)),
on an M1 Pro laptop, Guangdong grid:

| Project | Task | Duration | Energy | CO2e |
|---|---|---|---|---|
| pv-wind-power-forecast | ultra-short-term training, 14 stations × 16 horizons | 134 s | 2.29 Wh | 1.01 g |
| aiwp-china-verification | verification over 198k forecast pairs | 4 s | 0.03 Wh | 0.01 g |
| aiwp-china-verification | figures | 4 s | 0.03 Wh | 0.01 g |

One gram of CO2e for the heaviest job. That is the honest headline and it is not
a flattering one: gradient-boosted trees on a laptop cost roughly what boiling a
thimble of water costs. Publishing the number anyway is the point — a figure
only means something if it gets reported when it is small as well as when it is
large.

## Usage

```bash
pip install -e .          # installs codecarbon, typer and the `ledger` command

ledger run --label "…" --project repo -- <any command>   # measure and record
ledger run --region 四川 --label "…" --project repo -- …  # different grid
ledger report --out reports/green-ai.md                  # markdown ledger
ledger badge --project repo                              # one line for a README
ledger factors                                           # what is loaded, and from where
```

`ledger run` passes the command's exit code through, so it drops into a Makefile
without changing what a failure means.

## Scope

Local compute only: the CPU, GPU and memory of the machine the command runs on,
for the duration it runs. Not the manufacture of the hardware, not the network,
not anything the command calls out to. A number that excludes the embodied
carbon of a laptop is not a life-cycle assessment and is not presented as one.

## Layout

```
src/ledger/
  grid.py      the factors, their citation, and the refusal to geolocate
  measure.py   run something, record energy, record whether it was measured
  report.py    markdown ledger, measured and estimated kept apart
  cli.py       ledger run / report / badge / factors
tests/         16 tests
```

## Related repositories

- [pv-wind-power-forecast](https://github.com/Zhaohh0706/pv-wind-power-forecast) — PV and wind forecasting, priced against Chinese grid-code assessment
- [aiwp-china-verification](https://github.com/Zhaohh0706/aiwp-china-verification) — fixed-lead verification of physics and AI weather models at Chinese stations
- [cn-weather-cube](https://github.com/Zhaohh0706/cn-weather-cube) — point weather with units attached and sources named
