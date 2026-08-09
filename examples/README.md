# Reference examples

Every `correct.py` is an offline executable reference using deterministic fake
clients. It demonstrates a narrow control that unit tests can verify. It is not a
drop-in production integration.

Every `violation.py` is intentionally unsafe teaching material and is not imported
by the test suite.

| Area | Executable reference | Verified property |
|---|---|---|
| T1 | [`traceability/correct.py`](traceability/correct.py) | Observable call reconstruction through artifact references |
| T1 GraphRAG | [`traceability/graphrag_correct.py`](traceability/graphrag_correct.py) | Seed, hop, context, and source-node trace completeness |
| R | [`resilience/correct.py`](resilience/correct.py) | Bounded fallback and explicit unavailable result |
| U | [`unit-economics/correct.py`](unit-economics/correct.py) | Context-aware routing, cache scope, no caching of generated output |
| T1/S answer | [`support-answer-generator/correct.py`](support-answer-generator/correct.py) | Approved-source retrieval, citation validation, and abstention |
| S extraction | [`state-structure/correct.py`](state-structure/correct.py) | Shape, domain invariant, and evidence-reference validation |
| S agent | [`state-structure/sandbox_correct.py`](state-structure/sandbox_correct.py) | Validate-before-execute, authorization, effect limits, idempotency |
| T2 | [`testability/correct.py`](testability/correct.py) | Versioned baseline/candidate eval and abstention |

Run all evidence:

```bash
./trust verify
python3 -m unittest discover -s tests -v
```

Guarantee and non-guarantee boundaries are repeated in each directory README and
at the top of each executable reference.
