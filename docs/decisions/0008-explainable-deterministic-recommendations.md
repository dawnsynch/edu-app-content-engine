# ADR 0008: Explainable Deterministic Recommendations

## Status

Accepted.

## Context

Edu DawnSynch needs useful personalized feeds before it has enough consented interaction data to train or evaluate a machine-learned ranker. Recommendations must respect source policy, avoid restricted third-party metrics, remain understandable to learners and operators, and work for new profiles.

## Decision

Use a deterministic weighted ranker inside the modular monolith. Its normalized score is composed of:

- career relevance: 25%
- selected technology-domain relevance: 20%
- learner/content skill-level fit: 15%
- permitted internal quality assessment: 20%
- publication freshness: 10%
- bookmark and anonymized engagement signals: 10%

Every result returns component values, weights, contributions, and concise reasons. Content must pass the same active-source, approved-or-restricted-rights, retention, completed-enrichment, and safe-moderation gates used by public search. Dismissed items are excluded.

Cold-start profiles use neutral preference values, leaving quality, freshness, and skill fit to establish ordering. A deterministic greedy pass limits source and content-type concentration while retaining all candidates as a fallback.

Redis stores versioned ranked snapshots for five minutes. A preference, bookmark, dismissal, or engagement write increments the learner's recommendation version, making old keys unreachable immediately. Cache hits revalidate current source, retention, moderation, and display policy before returning content. Pagination cursors carry the profile version and offset; stale cursors are rejected.

Learners are represented by random UUIDs. Engagement events contain no name, email, IP address, user agent, free text, or arbitrary metadata.

## Consequences

- Ranking can be reproduced and audited without a model-training platform.
- Two learners can receive distinct feeds from the same policy-approved corpus.
- Cache invalidation is constant-time and does not require Redis key scans.
- UUID possession is not authentication. A future authentication phase must bind the anonymous profile to an authorized user before public production exposure.
- Weight changes require explicit code review and recommendation regression tests.
