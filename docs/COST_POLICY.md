# JARVIS Cost & Budget Policy

## Invariant 1: Budget Caps
JARVIS strictly enforces three budget ceilings via `CostGovernor`:
1. **Per-Task Limit**: Maximum $0.50 USD. Any task exceeding this threshold requires human authorization via `/model/approve-expensive-call`.
2. **Daily Limit**: Maximum $5.00 USD. Once reached, all Tier 3 cloud calls are blocked or routed to Tier 1/2.
3. **Monthly Limit**: Maximum $50.00 USD.

## Invariant 2: Free Local First
Tier 1 (Ollama) and Tier 2 (vLLM on private GPU) incur $0.00 marginal cost. The Model Router defaults to local execution whenever task quality permits.

## Invariant 3: Provider Circuit Breakers
If an external API provider encounters 3 consecutive failures (timeouts, 500 errors, rate limits), the circuit breaker trips for 60 seconds. Requests are safely queued or rerouted to local models.
