.PHONY: validate validate-metadata validate-bdd validate-messaging

validate:
	./scripts/validate-static.sh

validate-metadata:
	python scripts/validate_metadata.py --repositories-root ..

validate-bdd:
	python -m pytest tests/bdd

validate-messaging:
	python -m pytest tests/integration/test_elasticmq_transport.py
