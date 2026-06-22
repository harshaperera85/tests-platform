"""Metric / parameter normalization — the single source of truth for theta.

All IRT parameters and theta are normalized here through the mirt scoring service
(CLAUDE.md golden rule 4). Handles the D-scaling mismatch (catR D=1 vs mirt
D=1.702). Empty in Phase 0 — built once, before any engine consumes theta.
"""
