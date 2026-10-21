# Specification index

1. [Public repository and deployment boundaries](01_PUBLIC_REPOSITORY.md) governs publication, private resource handling and branch permissions.
2. [Input, defaults and clinical UI contract](06_V04_REPAIR_SPEC.md).
3. [Data, history and migration contract](07_V04_DATA_AND_MIGRATION.md).
4. [Presentation and administrator date permissions](09_ACCEPTANCE_PRESENTATION_AND_PERMISSIONS.md).
5. [0.4.2 repair rules](11_PUBLIC_QA_REPAIR_SPEC.md) and [acceptance criteria](12_PUBLIC_QA_REPAIR_ACCEPTANCE.md) override earlier behavior where specified.

The machine-readable clinical contract is `backend/app/domain/clinical_v03_contract.json`. It retains 51 original transitions and 7 approved supplemental transitions. Original stakeholder documents, historical approval conversations and local reports referenced in older specification prose are private project records, not repository dependencies. Publication boundaries above override earlier packaging language: source originals belong only in authorized private deployments, never in Git.

Change the applicable specifications before implementation. Do not infer new clinical decisions from code or change locked thresholds without an approved source.

Approved 0.4.3 overrides: [usability repairs](14_V043_USABILITY.md), [acceptance](15_V043_ACCEPTANCE.md). These restore the administrator's visible date entry, allow explicitly reviewed current-plan removal and improve date/result explanations without changing clinical thresholds or historical records.
