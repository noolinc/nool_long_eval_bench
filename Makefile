# One-command replication entry points (design spec §8).
#
#   make trackB    deterministic micro-benchmarks; free, no API keys
#   make summarize re-render all committed results as tables
#   make tier1     Track B + a 1-rep Track C smoke cell (costs LLM spend)
#   make trackC HARNESS=claude N=5 MODEL=<pinned-model-id>
#
# Containerized execution (spec §8): build once, record the image ID in
# provenance, then run the same targets inside the container.
#
#   make docker-build
#   make docker-digest          # print image ID to stamp into results
#   make docker-trackB          # mounts the local nool CLI read-only

HARNESS ?= claude
N ?= 5
MODEL ?=
MODEL_FLAG = $(if $(MODEL),--model $(MODEL),)
IMAGE ?= nool-benchmarks

.PHONY: trackB summarize tier1 trackC docker-build docker-digest docker-trackB check-transcripts

trackB:
	cd micro && python3 b1_overhead.py \
		&& python3 b2_concurrency.py \
		&& python3 b3_recovery.py \
		&& python3 b4_guardrails.py \
		&& python3 b5_swarm_merge.py \
		&& python3 b6_context_retrieval.py \
		&& python3 b7_regression_localization.py
	python3 analysis/summarize.py

summarize:
	python3 analysis/summarize.py

tier1: trackB
	cd harness && python3 run_experiment.py --harness $(HARNESS) $(MODEL_FLAG) \
		--tasks redux_go --cells all --reps 1

trackC:
	cd harness && python3 run_experiment.py --harness $(HARNESS) $(MODEL_FLAG) \
		--tasks redux_go --cells all --reps $(N)

check-transcripts:
	python3 analysis/transcript_manifest.py check

docker-build:
	docker build -t $(IMAGE) .

docker-digest:
	@docker image inspect $(IMAGE) --format 'sha256:{{.Id}}'

docker-trackB:
	docker run --rm -it \
		-v $$(pwd):/work -w /work \
		-v $$(which nool):/usr/local/bin/nool:ro \
		$(IMAGE) sh -c "make trackB"
