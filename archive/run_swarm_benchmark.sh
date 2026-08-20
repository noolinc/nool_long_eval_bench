#!/bin/bash
# Nool vs Git: Concurrent-Agent Merge Benchmark (REAL — no simulated/hardcoded output)
#
# Models N agents that worked concurrently from the same base commit and now need
# their branches integrated. Two scenarios are tested, each against a plain Git repo
# (git merge) and a Nool-tracked repo (nool merge, the documented path for ingesting
# a divergent branch — see `nool merge --help`):
#
#   DISJOINT  — each agent adds its own new file. No textual overlap.
#   CONTENDED — every agent inserts a new method at the *same* anchor line in one
#               shared file (the worst case for line-based text merging).
#
# Every number in the output/JSON comes from an actually-executed `git merge` or
# `nool merge` and its real exit code / wall-clock time. Nothing here is printed
# without having been run.

set -uo pipefail

N=${1:-15}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$ROOT/swarm_bench_work"
RESULTS_JSON="$ROOT/swarm_bench_results.json"

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"

BASE_GO='package server

type Server struct {
	running bool
}

func NewServer() *Server {
	return &Server{}
}

// AGENTS_INSERT_HERE
'

setup_repo() {
    local dir=$1
    mkdir -p "$dir"
    (
        cd "$dir"
        git init -q
        git config user.email swarm@test.local
        git config user.name "Swarm Bench"
        printf '%s' "$BASE_GO" > server.go
        git add server.go
        git commit -qm "base"
    )
}

make_branches_disjoint() {
    local dir=$1
    (
        cd "$dir"
        local base_branch
        base_branch=$(git symbolic-ref --short HEAD)
        for i in $(seq 1 "$N"); do
            git checkout -q -b "agent_$i" "$base_branch"
            echo "package server" > "agent_${i}_file.go"
            git add "agent_${i}_file.go"
            git commit -qm "agent $i: add own file"
            git checkout -q "$base_branch"
        done
    )
}

make_branches_contended() {
    local dir=$1
    (
        cd "$dir"
        local base_branch
        base_branch=$(git symbolic-ref --short HEAD)
        for i in $(seq 1 "$N"); do
            git checkout -q -b "agent_$i" "$base_branch"
            sed -i.bak "s#// AGENTS_INSERT_HERE#func (s *Server) Method${i}() {}\\
\\
// AGENTS_INSERT_HERE#" server.go
            rm -f server.go.bak
            git commit -qam "agent $i: add Method$i at shared anchor"
            git checkout -q "$base_branch"
        done
    )
}

# Runs `git merge agent_$i` for i in 1..N against $1, aborting cleanly on conflict.
# Prints: "<successes> <conflicts> <elapsed_seconds>"
run_git_merges() {
    local dir=$1
    local success=0 conflict=0
    local t0 t1
    t0=$(date +%s)
    (
        cd "$dir"
        for i in $(seq 1 "$N"); do
            if git merge -q --no-edit "agent_$i" > /dev/null 2>&1; then
                echo ok
            else
                git merge --abort > /dev/null 2>&1
                echo conflict
            fi
        done
    ) > "$WORKDIR/git_merge.$$.log"
    t1=$(date +%s)
    success=$(grep -c '^ok$' "$WORKDIR/git_merge.$$.log")
    conflict=$(grep -c '^conflict$' "$WORKDIR/git_merge.$$.log")
    rm -f "$WORKDIR/git_merge.$$.log"
    echo "$success $conflict $((t1 - t0))"
}

# Same as above but via `nool merge`, the ledger's PR-ingestion path.
run_nool_merges() {
    local dir=$1
    local success=0 conflict=0
    local t0 t1
    t0=$(date +%s)
    (
        cd "$dir"
        for i in $(seq 1 "$N"); do
            if nool merge "agent_$i" --compact > /dev/null 2>&1; then
                echo ok
            else
                git merge --abort > /dev/null 2>&1
                echo conflict
            fi
        done
    ) > "$WORKDIR/nool_merge.$$.log"
    t1=$(date +%s)
    success=$(grep -c '^ok$' "$WORKDIR/nool_merge.$$.log")
    conflict=$(grep -c '^conflict$' "$WORKDIR/nool_merge.$$.log")
    rm -f "$WORKDIR/nool_merge.$$.log"
    echo "$success $conflict $((t1 - t0))"
}

nool_dag_heads() {
    local dir=$1
    (cd "$dir" && nool status --compact 2>/dev/null | grep -m1 'DAG Heads' | grep -o '[0-9]\+')
}

echo "====================================================="
echo " Swarm Benchmark (real): N=$N concurrent agent branches"
echo "====================================================="

for scenario in disjoint contended; do
    for backend in git nool; do
        dir="$WORKDIR/${scenario}_${backend}"
        setup_repo "$dir"
        if [ "$scenario" = "disjoint" ]; then
            make_branches_disjoint "$dir"
        else
            make_branches_contended "$dir"
        fi
        if [ "$backend" = "nool" ]; then
            (cd "$dir" && nool init > /dev/null 2>&1)
            read -r succ conf secs < <(run_nool_merges "$dir")
            heads=$(nool_dag_heads "$dir")
        else
            read -r succ conf secs < <(run_git_merges "$dir")
            heads="n/a"
        fi
        eval "${scenario}_${backend}_success=$succ"
        eval "${scenario}_${backend}_conflict=$conf"
        eval "${scenario}_${backend}_seconds=$secs"
        eval "${scenario}_${backend}_dag_heads=$heads"
        echo ""
        echo "[$scenario / $backend] agents=$N  clean_merges=$succ  conflicts=$conf  wall_time=${secs}s  dag_heads_after=$heads"
    done
done

cat > "$RESULTS_JSON" <<EOF
{
  "agents": $N,
  "disjoint": {
    "git":  {"clean_merges": ${disjoint_git_success},  "conflicts": ${disjoint_git_conflict},  "wall_time_s": ${disjoint_git_seconds}},
    "nool": {"clean_merges": ${disjoint_nool_success}, "conflicts": ${disjoint_nool_conflict}, "wall_time_s": ${disjoint_nool_seconds}, "dag_heads_after": ${disjoint_nool_dag_heads}}
  },
  "contended": {
    "git":  {"clean_merges": ${contended_git_success},  "conflicts": ${contended_git_conflict},  "wall_time_s": ${contended_git_seconds}},
    "nool": {"clean_merges": ${contended_nool_success}, "conflicts": ${contended_nool_conflict}, "wall_time_s": ${contended_nool_seconds}, "dag_heads_after": ${contended_nool_dag_heads}}
  }
}
EOF

echo ""
echo "====================================================="
echo " Results written to $RESULTS_JSON"
echo "====================================================="
