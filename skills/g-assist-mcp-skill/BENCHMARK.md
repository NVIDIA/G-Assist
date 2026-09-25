# Skill Benchmark: g-assist-mcp-skill

> ✅ **Overall verdict: PASS on the CI suite**

This report is the Docker CI run of `evals/evals.json` only: 16 tasks, one attempt per agent, no GPU, and no G-Assist server. It does not cover modeset keep-or-revert, elicitation, live enums, or a failed change that still returns `isError: false`. Those cases are in `evals/evals-hardware.json` and are not scored here.

## Publication Recommendation

The CI suite passed. This table is not the hardware publication record. Add a hardware results table before using this report as evidence that display and GPU control is ready to publish.

## Evaluation Metadata

- Skill: `g-assist-mcp-skill`
- Evaluation date: 2026-09-22
- Evaluator version: `1.5.8`
- Agents: Claude Code (`aws/anthropic/bedrock-claude-opus-4-8`), Codex (`openai/openai/gpt-5.5`)
- Tasks: 16 evaluation tasks (11 positive, 5 negative)
- Dataset digest: `sha256:005ae43f3adb9fe981b27b5096c41379327675753c3c913e0df8734f6d3159f2` (skill-evaluator-dataset-snapshot/1)
- Attempts per task: 1
- Environment: `docker`
- Tier 2 evidence: required for publication
- Tier 3 evidence: required for publication

Each task attempt ran in its own isolated Docker container.

## What This Report Answers

The three-tier evaluation checks whether the skill:

- is safe to use;
- produces correct answers;
- is discovered and activated when needed;
- helps the agent complete the user's goal and expected workflow; and
- avoids wasted skill and tool usage.

## Results at a Glance

| Measure | Claude Code (Baseline → Skill Uplift) | Codex (Baseline → Skill Uplift) |
|---|---:|---:|
| Overall | 88.2% — baseline ran, but no comparable score was available; uplift unavailable | 95.8% — baseline ran, but no comparable score was available; uplift unavailable |
| Security | 100.0% → 100.0% (±0.0 points) | 93.8% → 100.0% (+6.2 points) |
| Correctness | 73.8% → 96.2% (+22.4 points) | 66.2% → 97.5% (+31.3 points) |
| Discoverability | 81.8% — baseline ran, but no comparable score was available; uplift unavailable | 93.6% — baseline ran, but no comparable score was available; uplift unavailable |
| Effectiveness | 72.9% → 79.3% (+6.4 points) | 61.0% → 89.5% (+28.5 points) |
| Efficiency | 83.7% — baseline ran, but no comparable score was available; uplift unavailable | 98.3% — baseline ran, but no comparable score was available; uplift unavailable |

**How to read this table:** baseline is the same task attempted without the target skill. Scores are rounded to one decimal; threshold-adjacent values use additional precision so their displayed band matches the verdict. Uplift is derived from those displayed scores and shown in percentage points.

Example: `47.0% → 92.0% (+45.0 points)` means the skill-assisted run scored 92.0%, 45.0 percentage points above its 47.0% no-skill baseline.

A partial dimension was calculated from only the available configured signals; review the detailed report before relying on it.

## Token Usage

Actual Tier 3 execution usage is reported for every observed agent/case pair and both conditions.

| Agent | Dataset case | With skill | Without skill | Delta | Change | Coverage |
|---|---|---:|---:|---:|---:|---|
| claude-code | All cases | 2,064,000 | 1,107,140 | +956,860 | +86.43% | skill 16/16; base 16/16 |
| claude-code | g-assist-mcp-skill-001 | 242,432 | 71,134 | +171,298 | +240.81% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-002 | 77,188 | 35,630 | +41,558 | +116.64% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-003 | 285,098 | 35,403 | +249,695 | +705.29% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-004 | 35,550 | 35,660 | -110 | -0.31% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-005 | 35,307 | 35,399 | -92 | -0.26% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-006 | 77,394 | 72,015 | +5,379 | +7.47% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-007 | 285,853 | 35,514 | +250,339 | +704.90% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-008 | 290,014 | 35,644 | +254,370 | +713.64% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-009 | 77,016 | 35,711 | +41,305 | +115.66% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-010 | 77,099 | 143,810 | -66,711 | -46.39% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-011 | 76,402 | 35,178 | +41,224 | +117.19% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-neg-001 | 35,069 | 34,990 | +79 | +0.23% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-neg-002 | 180,317 | 214,029 | -33,712 | -15.75% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-neg-003 | 218,152 | 180,135 | +38,017 | +21.10% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-neg-004 | 35,559 | 71,224 | -35,665 | -50.07% | skill 1/1; base 1/1 |
| claude-code | g-assist-mcp-skill-neg-005 | 35,550 | 35,664 | -114 | -0.32% | skill 1/1; base 1/1 |
| codex | All cases | 757,574 | 684,630 | +72,944 | +10.65% | skill 16/16; base 16/16 |
| codex | g-assist-mcp-skill-001 | 41,908 | 51,244 | -9,336 | -18.22% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-002 | 42,435 | 24,773 | +17,662 | +71.30% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-003 | 56,972 | 81,635 | -24,663 | -30.21% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-004 | 27,061 | 12,053 | +15,008 | +124.52% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-005 | 42,026 | 12,080 | +29,946 | +247.90% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-006 | 41,899 | 39,335 | +2,564 | +6.52% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-007 | 41,962 | 49,551 | -7,589 | -15.32% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-008 | 42,955 | 24,918 | +18,037 | +72.39% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-009 | 41,885 | 37,917 | +3,968 | +10.46% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-010 | 60,598 | 87,921 | -27,323 | -31.08% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-011 | 42,281 | 24,475 | +17,806 | +72.75% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-neg-001 | 11,736 | 11,665 | +71 | +0.61% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-neg-002 | 64,269 | 64,220 | +49 | +0.08% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-neg-003 | 92,507 | 74,224 | +18,283 | +24.63% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-neg-004 | 50,520 | 37,587 | +12,933 | +34.41% | skill 1/1; base 1/1 |
| codex | g-assist-mcp-skill-neg-005 | 56,560 | 51,032 | +5,528 | +10.83% | skill 1/1; base 1/1 |
| ALL AGENTS | Dataset aggregate | 2,821,574 | 1,791,770 | +1,029,804 | +57.47% | skill 32/32; base 32/32 |

Prompt tokens include cached reads, so total tokens are `prompt + completion` (cached is not added twice). The Efficiency score uses `(prompt - cached) + completion`. N/A means the relevant trajectory counters were not available; coverage is never estimated.

## Tier Status

| Tier | Purpose | Status | Evidence |
|---|---|---|---|
| Tier 1 | Static validation | **PASSED** | 11 validator(s); 0 finding(s) |
| Tier 2 | Semantic deduplication | **PASSED** | 2 validator(s); 0 finding(s) |
| Tier 3 | Live agent evaluation | **PASS** | 2 agent(s); 16 task(s) |

## Findings and Observations

<details>
<summary>Show detailed findings and successful checks</summary>

- Schema & Repository Governance: Found skill manifest: SKILL.md
- Semantic Version Validation: Valid semantic version: 1.0.0
- Security Scan: No security vulnerabilities detected (secrets, API keys, credentials)
- PII Scan: Scanning 1 files for PII
- Code Integrity & Hygiene: Checking 1 markdown files for dead links
- Unicode Smuggling Detection: No invisible Unicode characters detected in 1 file(s)
- QUALITY: Score: 100.0/100 (Grade: A)
- SCRIPT_LINT: No scripts/ directory found
- Context Deduplication: Collected 1 file(s)
- AGENT_EVAL: Tier 3 evaluation complete: verdict PASS; best agent codex

</details>

## Scoring Methodology

<details>
<summary>Show dimension definitions, source signals, and thresholds</summary>

| Dimension | Question | Scored signals |
|---|---|---|
| Security | Is it safe to use? | `security` (100%) |
| Correctness | Is the answer correct? | `accuracy` (100%) |
| Discoverability | Was the right skill loaded when needed? | `skill_execution` (100%) |
| Effectiveness | Did the skill help complete the task? | `goal_accuracy` (50%) + `behavior_check` (50%) |
| Efficiency | Did it avoid wasted tool calls and token usage? | `skill_efficiency` (50%) + `token_efficiency` (50%) |

- Dimension bands: PASS at 50% or above; NEUTRAL from 40% to below 50%; FAIL below 40%.
- Overall Tier 3 lift: PASS at +5 points or more; FAIL at -10 points or less; values between those bands are NEUTRAL.
- Overall verdict: PASS only when every configured dimension passes for at least one supported agent. Lift is reported as diagnostic evidence and does not override this gate.
- The 50% attempt pass threshold is a separate per-task gate; it is not the dimension pass threshold.
- Effectiveness is the equal-weight mean of goal completion (`goal_accuracy`) and expected workflow adherence (`behavior_check`).
- Efficiency is 50% tool-call productivity (the backward-compatible `skill_efficiency` wire id) and 50% `token_efficiency`. Positive-case skill routing is scored under Discoverability, not Efficiency; a negative case without a routing target is N/A. N/A sources are omitted, remaining weights are renormalized, and the dimension is marked partial.

Signals present in this run:

- `security` (Security): unsafe operations, secret leakage, and unauthorized access.
- `skill_execution` (Skill Execution): whether the expected skill was selected, decoys were avoided, and the workflow executed.
- `skill_efficiency` (Tool Productivity): tool-call productivity (legacy wire id; routing is scored under Discoverability).
- `accuracy` (Accuracy): final-answer correctness against the reference answer.
- `goal_accuracy` (Goal Accuracy): whether the user's goal was achieved.
- `behavior_check` (Behavior Check): whether the expected workflow behavior was followed.
- `token_efficiency` (Token Efficiency): actual uncached prompt plus completion usage (50% of Efficiency).

</details>

## Freshness

Regenerate this benchmark when the skill, evaluation dataset, target agent/model, evaluator version, environment, or scoring policy changes.
