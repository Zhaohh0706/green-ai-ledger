PY := python
SRC := PYTHONPATH=src $(PY)

.PHONY: report badge factors test

report:
	$(SRC) -m ledger.cli report --out reports/green-ai.md

badge:
	$(SRC) -m ledger.cli badge

factors:
	$(SRC) -m ledger.cli factors

test:
	$(SRC) -m pytest tests -q
