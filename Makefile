.PHONY: test example check clean

PY ?= python3

test:            ## semantic + end-to-end gate tests
	$(PY) -m unittest discover -s tests -v

example:         ## run the shipped worked example through W and C in a throwaway project
	@rm -rf projects/example-run && $(PY) bin/wckd.py new example-run "Air quality monitor" >/dev/null
	@cp examples/air-quality-monitor/brief.json examples/air-quality-monitor/landscape.json projects/example-run/
	@$(PY) bin/wckd.py gate example-run G-W --by conductor --human >/dev/null
	@$(PY) bin/wckd.py gate example-run G-C --by conductor | head -3
	@$(PY) bin/wckd.py score example-run | tail -4
	@rm -rf projects/example-run

check: test example   ## everything a merge must pass

clean:
	@rm -rf projects/example-run __pycache__ tests/__pycache__ bin/__pycache__
