.PHONY: validate validate-metadata validate-bdd

validate:
	./scripts/validate-static.sh

validate-metadata:
	python scripts/validate_metadata.py --repositories-root ..

validate-bdd:
	python -m pytest tests/bdd
