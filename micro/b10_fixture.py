"""B10 part 2 fixture: a synthetic Go repository of controllable size R
(number of packages) with one target cluster per fan-in level D, so the
change surface S = D is independent of the repository size R.

Each package is exactly one non-test source file: Go's same-package call
resolution has since been fixed in Nool (was zero-edge; verified stale by
the admission-control session), but keeping one source file per package
still guarantees every dependency is a real cross-package `import`, which
is what the propose-time envelope actually walks (Uses/Calls/DependsOn),
rather than same-file/same-package locality the graph doesn't touch.

Layout for R packages and D-levels (0, 4, 16, 64):
  go.mod
  t<D>/t<D>.go              target function F_t<D>()
  t<D>/t<D>_test.go          external test package, imports t<D> (a real edge)
  t<D>_dep_<j>/dep.go        imports t<D>, calls F_t<D>() -- j in [0, D)
  t<D>_dep_<j>/dep_test.go   external test package for the leaf
  f_<i>/f.go                 filler; imports f_<i-1>, f_<i-2> (real edges, no target)
  f_<i>/f_test.go            filler test

Ground truth by construction, independent of R: for target t<D>,
  dependents closure   = D leaf sources + D leaf tests + t<D>'s own test = 2D + 1 files
  propose envelope     = touched file + closure                          = 2D + 2
  affected tests       = D leaf tests + t<D>'s own test                  = D + 1
Fillers are disjoint from every target cluster and from each other's
targets; nothing in a filler reaches a target.
"""

from pathlib import Path

D_LEVELS = (0, 4, 16, 64)
FILLER_FAN_OUT = 2


def _pkg_go(name: str, fn: str, body: str, imports: list[str] | None = None) -> str:
    imp = ""
    if imports:
        lines = "\n".join(f'\t"bench/{p}"' for p in imports)
        imp = f"import (\n{lines}\n)\n\n"
    return f"package {name}\n\n{imp}func {fn}() int {{\n\t{body}\n}}\n"


def _test_go(pkg: str, fn: str) -> str:
    return (
        f'package {pkg}_test\n\n'
        f'import (\n\t"testing"\n\n\t"bench/{pkg}"\n)\n\n'
        f"func Test{fn}(t *testing.T) {{\n"
        f"\tif {pkg}.{fn}() <= 0 {{\n\t\tt.Fatal(\"unexpected\")\n\t}}\n}}\n"
    )


def target_symbol(d: int) -> str:
    return f"F_t{d}"


def target_closure_files(d: int) -> list[str]:
    """The 2D+1 files a change to t<d>/t<d>.go is expected to reach."""
    files = [f"t{d}/t{d}_test.go"]
    for j in range(d):
        files.append(f"t{d}_dep_{j}/dep.go")
        files.append(f"t{d}_dep_{j}/dep_test.go")
    return files


def generate(root: Path, r_packages: int, d_levels: tuple[int, ...] = D_LEVELS,
             filler_fan_out: int = FILLER_FAN_OUT) -> dict:
    """Write the fixture under `root`. Returns a manifest with per-D ground
    truth and the filler/target package counts, for the runner and for
    provenance in the emitted results."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "go.mod").write_text("module bench\n\ngo 1.21\n")

    reserved = 0
    for d in d_levels:
        reserved += 1 + d  # t<d> itself + its D leaf importers

    n_fillers = max(0, r_packages - reserved)

    # Targets and their leaf dependents.
    for d in d_levels:
        tdir = root / f"t{d}"
        tdir.mkdir(exist_ok=True)
        fn = target_symbol(d)
        (tdir / f"t{d}.go").write_text(_pkg_go(f"t{d}", fn, "return 1"))
        (tdir / f"t{d}_test.go").write_text(_test_go(f"t{d}", fn))
        for j in range(d):
            ddir = root / f"t{d}_dep_{j}"
            ddir.mkdir(exist_ok=True)
            leaf_fn = f"G_t{d}_{j}"
            body = f'return t{d}.{fn}() + 1'
            (ddir / "dep.go").write_text(
                f'package t{d}_dep_{j}\n\nimport "bench/t{d}"\n\n'
                f"func {leaf_fn}() int {{\n\t{body}\n}}\n"
            )
            (ddir / "dep_test.go").write_text(_test_go(f"t{d}_dep_{j}", leaf_fn))

    # Fillers: each imports up to `filler_fan_out` earlier fillers (real
    # cross-package edges, real O(R) edge count), never a target. The body
    # references the imported functions without calling them: calling both
    # made H_i a cross-package Fibonacci (fib(i) calls), so `go test ./...`
    # never finished past i ~ 45 and the timed-out warm-up leaked spinning
    # test binaries (bug b0d15306). Each test must stay O(1).
    for i in range(n_fillers):
        fdir = root / f"f_{i}"
        fdir.mkdir(exist_ok=True)
        deps = [f"f_{i - k}" for k in range(1, filler_fan_out + 1) if i - k >= 0]
        fn = f"H_{i}"
        if deps:
            refs = ", ".join(f"f_{i - k}.H_{i - k}" for k in range(1, filler_fan_out + 1) if i - k >= 0)
            body = f"return 1 + len([]func() int{{{refs}}})"
        else:
            body = "return 1"
        (fdir / "f.go").write_text(_pkg_go(f"f_{i}", fn, body, imports=deps))
        (fdir / "f_test.go").write_text(_test_go(f"f_{i}", fn))

    manifest = {
        "r_packages_requested": r_packages,
        "d_levels": list(d_levels),
        "n_fillers": n_fillers,
        "n_targets": len(d_levels),
        "n_leaf_packages": reserved - len(d_levels),
        "total_packages": n_fillers + reserved,
        "total_files": (n_fillers + reserved) * 2 + 1,  # +1 for go.mod
        "ground_truth": {
            str(d): {
                "target_symbol": target_symbol(d),
                "target_file": f"t{d}/t{d}.go",
                "closure_files_expected": 2 * d + 1,
                "envelope_expected": 2 * d + 2,
                "affected_tests_expected": d + 1,
                "closure_files": target_closure_files(d),
            }
            for d in d_levels
        },
    }
    return manifest
