# Incident Evidence Timeline: Making Incident Data Trustworthy Before AI Analysis

Incident response depends on sequence. A deployment, an error-rate alarm, a customer ticket, and a rollback may all describe the same event, but their source systems can disagree about time and identity.

![Incident Evidence Timeline architecture](https://raw.githubusercontent.com/ohjeffkuston/incident-evidence-timeline/main/docs/architecture.png)

## The operational problem

Modern responders collect evidence from cloud monitoring, deployment pipelines, service desks, and application logs. Those systems use different formats and may have small clock offsets. Duplicate deliveries are common, and quiet periods may represent either a real gap or missing telemetry.

Passing that raw stream directly to an AI incident assistant creates a subtle risk: the model can write a convincing narrative around an incorrect chronology.

## A deterministic evidence layer

I built **Incident Evidence Timeline** to normalize the evidence before interpretation. The Python engine applies declared source clock corrections, converts every timestamp to UTC, removes exact duplicates, fails closed when one event identity carries conflicting evidence, and sorts the final chronology with stable tie-breaking.

It also detects intervals longer than an approved threshold. A complete sequence returns `READY`; a timeline with material gaps returns `REVIEW` so a human can investigate before the report reaches an AI summarizer or post-incident workflow.

## Why this matters for AI orchestration

LLMs are useful for explanation, synthesis, and questions. They should not be responsible for silently repairing source evidence. Deterministic preprocessing creates a clearer boundary: code establishes the chronology; the model interprets the resulting evidence; humans retain authority over conclusions and remediation.

The repository includes ten unit tests, synthetic data, GitHub Actions CI, Docker guidance, and an inactive n8n workflow.

## The safety boundary

The project makes no external calls, stores no credentials, changes no infrastructure, and performs no remediation. It generates a structured evidence report only. Real integrations should use read-only exports, immutable raw records, controlled storage, and explicit human review.

Source code, tests, architecture, and deployment guidance:

https://github.com/ohjeffkuston/incident-evidence-timeline

