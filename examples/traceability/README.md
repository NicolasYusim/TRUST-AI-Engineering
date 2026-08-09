# Traceability examples

## Guarantees

- The summarizer reference stores resolvable input, instruction, and output
  artifacts and links them to one run.
- The GraphRAG reference records seed resolution, every selected graph edge,
  graph version, context node IDs, and answer source IDs.

## Does not guarantee

- factual correctness or source quality;
- byte-identical replay from a real provider;
- production-grade security of the in-memory artifact store;
- access-control or retention compliance outside the adapter.
