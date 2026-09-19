# data/boards.json is the canonical, generated registry. Lambda packaging needs
# it inside the function directory, so it is copied in at build time rather than
# duplicated in the repo.
.PHONY: build deploy sync-data test clean

sync-data:
	cp data/boards.json backend/functions/ingest/boards.json

build: sync-data
	sam build

deploy: build
	sam deploy --guided

test:
	.venv/bin/python -m pytest tests/ -q

clean:
	rm -rf .aws-sam backend/functions/ingest/boards.json
