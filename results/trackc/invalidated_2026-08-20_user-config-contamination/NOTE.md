# Invalidated: user-config contamination

These 8+ runs (2026-08-20, `claude-sonnet-5`) are excluded from all analysis.

**Cause:** agent sessions were launched without settings isolation, so the
operator's user-level Claude Code configuration leaked in — plugins, skills,
personal hooks. Transcripts show agents invoking a user-installed skill
(`superpowers:brainstorming`) whose instructions require presenting a design
and awaiting human approval before writing code; in headless mode no approval
can arrive, so affected runs produced a design and stopped without writing
any file (observed in `single_git` r1/r2: 3–4 turns, zero file writes,
hidden-test failure). All cells in this batch are contaminated in principle,
including passing ones.

**Fix:** the claude adapter now passes `--setting-sources project,local`,
excluding user-level configuration while keeping project-level settings (the
nool arm's workspace hooks are the treatment under test). The full grid was
rerun from scratch after the fix; only post-fix data is analyzed.

Retained verbatim (records + transcripts) as evidence of the failure mode:
environment isolation between the benchmark operator's tooling and the
system under test is a validity requirement, not a nicety.
