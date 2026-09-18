"""Command line: measure a command, then report the ledger.

    ledger run --label "A1 benchmark" --project pv-wind -- make bench
    ledger report --out reports/green-ai.md
    ledger badge --project pv-wind
"""
from __future__ import annotations

import sys
from pathlib import Path

import typer

from . import measure, report as report_module
from .grid import FACTORS, SOURCE

app = typer.Typer(add_completion=False, help=__doc__)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    label: str = typer.Option(..., "--label", "-l", help="What this run is"),
    project: str = typer.Option(..., "--project", "-p", help="Which project it belongs to"),
    region: str = typer.Option("广东", "--region", help="Grid region the machine draws from"),
    cwd: str = typer.Option(None, "--cwd", help="Directory to run in"),
) -> None:
    """Run a command and record what it cost."""
    command = list(ctx.args)
    if not command:
        typer.secho("nothing to run; put the command after --", fg="red")
        raise typer.Exit(code=2)

    measured, note = measure.power_measurement_available()
    typer.secho(
        f"energy: {'measured' if measured else 'estimated'} ({note})",
        fg="green" if measured else "yellow",
    )

    record = measure.run_command(command, label, project, region, cwd=cwd)
    typer.echo(
        f"\n{record.label}: {record.duration_s:.1f} s, "
        f"{record.energy_kwh * 1000:.2f} Wh, {record.co2_g:.2f} g CO2 "
        f"at {record.grid_factor_kg_per_kwh} kgCO2/kWh ({record.region})"
    )
    if record.exit_code:
        typer.secho(f"command exited {record.exit_code}", fg="yellow")
    raise typer.Exit(code=record.exit_code or 0)


@app.command()
def report(
    out: Path = typer.Option(None, "--out", "-o", help="Write the markdown report here"),
) -> None:
    """Summarise the ledger."""
    records = measure.load()
    if not records:
        typer.secho("ledger is empty; run something first", fg="yellow")
        raise typer.Exit(code=1)
    text = report_module.to_markdown(records)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        typer.echo(f"wrote {out}")
    else:
        typer.echo(text)


@app.command()
def badge(project: str = typer.Option(None, "--project", "-p")) -> None:
    """Print the one-line summary a README can carry."""
    records = measure.load()
    if project:
        records = [r for r in records if r.project == project]
    if not records:
        typer.secho("no records for that project", fg="yellow")
        raise typer.Exit(code=1)
    typer.echo(report_module.badge_line(records))


@app.command()
def factors() -> None:
    """Show the grid factors available and where they come from."""
    for region, factor in FACTORS.items():
        typer.echo(f"  {region:6s} {factor.value:<8g} kgCO2/kWh  [{factor.level}]")
    typer.echo(f"\n{SOURCE['issuer']}，{SOURCE['name']}，{SOURCE['published']}")
    typer.echo(f"{SOURCE['url']}")
    typer.echo(f"sha256 {SOURCE['sha256']}")


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(main())
