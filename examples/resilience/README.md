# Resilience example

## Guarantees

- The primary and secondary routes are attempted in a deterministic bounded order.
- Invalid or temporarily unavailable routes do not leak a candidate as valid.
- Exhaustion returns an explicit unavailable result.

## Does not guarantee

- generated-code functionality;
- safe execution of returned text;
- equivalent quality across providers;
- production timeout, circuit-breaker, or concurrency behavior.
