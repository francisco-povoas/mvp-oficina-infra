.PHONY: validate validate-metadata validate-bdd test-bdd validate-messaging validate-checkpoint-e \
	checkpoint-a-build checkpoint-a-up checkpoint-a-validate checkpoint-a-status \
	checkpoint-a-logs checkpoint-a-down checkpoint-b-up checkpoint-b-validate \
	checkpoint-b-status checkpoint-b-logs checkpoint-b-down \
	checkpoint-c-build checkpoint-c-up checkpoint-c-validate checkpoint-c-status \
	checkpoint-c-logs checkpoint-c-down

validate:
	./scripts/validate-static.sh

validate-metadata:
	python scripts/validate_metadata.py --repositories-root ..

validate-bdd:
	python -m pytest tests/bdd

test-bdd:
	./scripts/run-bdd.sh

validate-messaging:
	python -m pytest tests/integration/test_elasticmq_transport.py

validate-checkpoint-e:
	./scripts/run-checkpoint-e.sh

checkpoint-a-build:
	./scripts/checkpoint-a.sh build

checkpoint-a-up:
	./scripts/checkpoint-a.sh up

checkpoint-a-validate:
	./scripts/checkpoint-a.sh validate

checkpoint-a-status:
	./scripts/checkpoint-a.sh status

checkpoint-a-logs:
	./scripts/checkpoint-a.sh logs

checkpoint-a-down:
	./scripts/checkpoint-a.sh down

checkpoint-b-up:
	./scripts/checkpoint-b.sh up

checkpoint-b-validate:
	./scripts/checkpoint-b.sh validate

checkpoint-b-status:
	./scripts/checkpoint-b.sh status

checkpoint-b-logs:
	./scripts/checkpoint-b.sh logs

checkpoint-b-down:
	./scripts/checkpoint-b.sh down

checkpoint-c-build:
	./scripts/checkpoint-c.sh build

checkpoint-c-up:
	./scripts/checkpoint-c.sh up

checkpoint-c-validate:
	./scripts/checkpoint-c.sh validate

checkpoint-c-status:
	./scripts/checkpoint-c.sh status

checkpoint-c-logs:
	./scripts/checkpoint-c.sh logs

checkpoint-c-down:
	./scripts/checkpoint-c.sh down
