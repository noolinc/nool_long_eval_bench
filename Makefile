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
.PHONY: trackB summarize tier1 trackC validate-study validate-harness validate-scorers docker-build docker-digest docker-trackB check-transcripts b10 b10-sanity b10-self b10-freeze

# Scorer validation: injected refusals, no-ops, partial landings and
# heading-only answers must be detected before any result is regenerated.
validate-scorers:
	cd micro && python3 validate_scorers.py

trackB: validate-scorers
	cd micro && python3 b1_overhead.py \
		&& python3 b2_concurrency.py \
		&& python3 b3_recovery.py \
		&& python3 b4_guardrails.py \
		&& python3 b5_swarm_merge.py \
		&& python3 b6_context_retrieval.py \
		&& python3 b7_regression_localization.py \
		&& python3 b8_blast_false_positive.py \
		&& python3 b9_blast_multilang.py
	python3 analysis/summarize.py

summarize:
	python3 analysis/summarize.py

# B10: admission cost C(R, S) -- repository size R vs semantic change surface
# S, held independent by construction. Opt-in, not part of trackB: b10 builds
# a synthetic fixture up to R=10,000 packages (the R=10k `nool init` is the
# long pole; fixtures are snapshotted under work/b10_snapshots/ and restored
# on re-runs) and b10-self copies the Nool repo named by B10_SOURCE_REPO.
# Both run ONE frozen binary, work/bin/nool (make b10-freeze copies the
# installed release there); a dirty, cargo-target or mid-run-replaced binary
# invalidates the result. b10-sanity is a 2-minute smoke run whose output
# goes to work/b10_sanity/, never results/.
B10_R ?= 100,1000,10000
B10_FREEZE_FROM ?= $(shell command -v nool)

b10-freeze:
	mkdir -p work/bin && cp "$(B10_FREEZE_FROM)" work/bin/.nool.tmp \
		&& chmod 755 work/bin/.nool.tmp && mv -f work/bin/.nool.tmp work/bin/nool
	work/bin/nool version --json && shasum -a 256 work/bin/nool

b10: validate-scorers
	cd micro && B10_R=$(B10_R) python3 b10_assurance_scaling.py

b10-sanity: validate-scorers
	cd micro && B10_R=100 B10_D=0,4 B10_REPS=1 B10_RESULTS_DIR=../work/b10_sanity \
		python3 b10_assurance_scaling.py

b10-self:
	cd micro && python3 b10_self.py

# Cost-effectiveness over the fleet records (review 2026-09-07 §4): break-even
# rework cost per matched cell. Numbers only. Override the cost parameters
# on the command line, e.g. make cost C_HOUR=100 FEE=5
C_HOUR ?= 0
C_POISON ?= 0
FEE ?= 0
cost:
	python3 analysis/cost_effectiveness.py --model claude-sonnet-5 --min-reps 2 \
		--c-hour $(C_HOUR) --c-poison $(C_POISON) --fee $(FEE)

tier1: trackB
	cd harness && python3 run_experiment.py --harness $(HARNESS) $(MODEL_FLAG) \
		--tasks redux_go --cells all --reps 1

trackC:
	cd harness && python3 run_experiment.py --harness $(HARNESS) $(MODEL_FLAG) \
		--tasks redux_go --cells all --reps $(N)

check-transcripts:
	python3 analysis/transcript_manifest.py check

validate-study:
	python3 harness/validate_protocol.py \
		tasks/fleet_service/tickets.json \
		tasks/fleet_service/tickets_v2.json \
		tasks/fleet_service/tickets_v3.json
	python3 -m py_compile harness/fleet_run.py harness/protocol.py \
		harness/validate_protocol.py analysis/summarize.py
	cd harness && python3 -m unittest -v test_protocol.py
	git diff --check

# End-to-end harness plumbing check, no LLM, ~3 min: every arm once with the
# deterministic scripted adapter. Records go to validation_runs.jsonl and are
# excluded from evidence by protocol rule.
validate-harness:
	python3 harness/fleet_run.py --harness scripted --model scripted \
		--arms git_fleet,git_retry,git_competitive,git_gated_queue,git_scheduled,nool_fleet,nool_gated,nool_try,nool_planned,git_planned,nool_native \
		--workers 8 --seed 7 --tickets tickets.json

docker-build:
	docker build -t $(IMAGE) .

docker-digest:
	@docker image inspect $(IMAGE) --format 'sha256:{{.Id}}'

docker-trackB:
	docker run --rm -it \
		-v $$(pwd):/work -w /work \
		-v $$(which nool):/usr/local/bin/nool:ro \
		$(IMAGE) sh -c "make trackB"
