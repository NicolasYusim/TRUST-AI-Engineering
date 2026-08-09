# T.R.U.S.T. crosswalk

This crosswalk helps engineers connect T.R.U.S.T. controls to broader frameworks.
It is informative, non-exhaustive, versioned, and not evidence of compliance or
certification.

Referenced baselines:

- [NIST AI RMF 1.0 and Generative AI Profile](https://www.nist.gov/itl/ai-risk-management-framework)
- [OWASP Top 10 for LLM and Generative AI Applications 2025](https://genai.owasp.org/llm-top-10/)
- [Google Secure AI Framework](https://www.saif.google/secure-ai-framework)
- [ISO/IEC 42001:2023 overview](https://www.iso.org/standard/42001)

## High-level mapping

| T.R.U.S.T. | NIST AI RMF | OWASP GenAI 2025 | Google SAIF | ISO/IEC 42001 themes |
|---|---|---|---|---|
| T1 Traceability & Attribution | GOVERN, MAP, MEASURE | Improper Output Handling, Misinformation, Vector/Embedding Weaknesses | Data/model/application provenance and monitoring | Documented information, traceability, monitoring |
| R Resilience & Ownership | GOVERN, MANAGE | Unbounded Consumption, Supply Chain | Infrastructure/application resilience and incident controls | Roles, operational control, corrective action |
| U Utility & Bounds | MAP, MEASURE, MANAGE | Unbounded Consumption | Resource and application controls | Objectives, resources, performance evaluation |
| S Scope & Structure | MAP, MANAGE | Prompt Injection, Sensitive Information Disclosure, Supply Chain, Data/Model Poisoning, Improper Output Handling, Excessive Agency, System Prompt Leakage | Data, infrastructure, model, application, and agent controls | Risk treatment, operational planning and control |
| T2 Testability & Oversight | GOVERN, MEASURE, MANAGE | Testing mitigations across all listed risks | Risk assessment, validation, monitoring | Performance evaluation, internal review, improvement |

## How to use the crosswalk

1. Start from the organization's applicable standard and scoped requirement.
2. Use this table to find candidate engineering controls.
3. Record the exact requirement and evidence in the component's governance system.
4. Do not infer that a passing `trust lint` satisfies the external requirement.
5. Re-review mappings when the referenced framework version changes.

## Known gaps

T.R.U.S.T. does not fully cover organizational governance, workforce competence,
fundamental-rights assessment, procurement, environmental impact, model training
governance, legal roles, or every security control. Those remain in the parent
frameworks and applicable law.
