# Day 11 Learning Guide — Incident Evidence Timeline

To: ohjeffkuston@yahoo.ca

## What you built

Incident Evidence Timeline is a deterministic Python tool that converts cloud alerts, deployment events, and service-desk evidence into a normalized incident chronology. It is designed to run before an AI incident assistant so the model receives ordered, traceable evidence instead of an ambiguous raw stream.

## Architecture walkthrough

1. **Evidence sources** provide synthetic event records with source name, event ID, timestamp, severity, service, type, and message.
2. **Input validation** rejects missing fields, unknown sources, invalid severities, naive timestamps, excessive clock offsets, and conflicting identities.
3. **Normalization** converts timestamps to UTC and subtracts each declared source clock offset.
4. **Deduplication** removes exact re-deliveries but fails closed when the same source and ID contain different evidence.
5. **Sequencing** orders events deterministically by normalized timestamp, source, and ID.
6. **Gap analysis** flags intervals larger than the configured threshold.
7. **Output** returns evidence fingerprints, counts, gaps, the ordered timeline, and a `READY` or `REVIEW` decision.

## Deploy it yourself

```bash
git clone https://github.com/ohjeffkuston/incident-evidence-timeline.git
cd incident-evidence-timeline
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m incident_evidence_timeline examples/incident-events.json
```

Docker option:

```bash
docker build -t incident-evidence-timeline .
docker run --rm -v "$PWD/examples:/evidence:ro" incident-evidence-timeline /evidence/incident-events.json
```

The sample intentionally returns `REVIEW`, so exit code 1 is expected.

## How to explain the code

- `_source_offsets` creates a trusted lookup and rejects duplicates or offsets beyond one hour.
- `_parse_timestamp` requires timezone-aware ISO-8601 values and normalizes them to UTC.
- `_fingerprint` creates a stable evidence identifier from required fields.
- `build_timeline` deep-copies the input, validates events, corrects clocks, handles duplicates, sorts the chronology, detects gaps, and builds the report.
- `cli.py` keeps operational behavior simple: exit 0 for `READY`, 1 for `REVIEW`, and 2 for unsafe input.

## Safe production extension

- Export events through read-only APIs or controlled collectors.
- Preserve raw records immutably and store normalized reports separately.
- Measure clock offsets from telemetry; never invent them.
- Add schema versioning, signed evidence, and durable storage.
- Use the normalized report as context for an LLM, not as permission to remediate.
- Keep remediation in an independently authorized workflow with human approval.

## Interview positioning

Use this project to discuss how you separate deterministic operational controls from probabilistic AI reasoning. Explain that the tool solves a real SRE problem—trustworthy chronology—while remaining testable, auditable, and safe. Highlight Python, CI/CD, incident response, data normalization, Docker, n8n, evidence integrity, and human-in-the-loop design.

## Questions to practise

1. Why is clock correction applied before sorting?
2. Why does a conflicting duplicate fail closed instead of choosing one event?
3. How would you ingest CloudWatch and deployment events without broad credentials?
4. Where would an LLM fit, and what should remain deterministic?
5. How would you preserve evidence integrity during a regulated incident review?

