.PHONY: test compile check

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

compile:
	PYTHONPATH=src python3 -m compileall -q src tests

check: test compile
