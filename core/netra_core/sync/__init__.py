"""NETRA sync — offline-first evidence sync (spec stage 8).

client.py: drains the on-device evidence ledger to the institutional
gateway (stdlib urllib transport; injectable for tests).
exporters.py: e-Daakhil / NCH 1915 standardized payload builders.

Deliberately NOT a per-scan pipeline stage: the spec defines stage 8 as
asynchronous, off the statutory critical path. run_scan never blocks on
connectivity; ping advertises the capability as capabilities.sync.
"""
