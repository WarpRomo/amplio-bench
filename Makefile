.PHONY: test compile shell check

test:
	PYTHONPATH=src python3 -W error -m unittest discover -s tests -v

compile:
	PYTHONPATH=src python3 -W error -m compileall -q src tests

shell:
	@for f in scripts/*.sh; do bash -n "$$f"; done

check: test compile shell
