# Public regression baselines

`frozen_output_templates.json` contains the 30 locked output texts already present in the application. `clinical_source_contract.json` contains only the 51 original transition fields already implemented by the clinical contract and the source workbook hash. Both were extracted from the previously verified private source documents at publication time, not generated from the application under test.

The original documents are excluded. Public baseline checks cannot be described as a new original-document comparison. Test patients and credentials elsewhere in this suite are isolated synthetic fixtures; no fixture is imported into the deployed database.
