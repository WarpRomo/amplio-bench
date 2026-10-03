# Validity

Long-horizon benchmarks create additional failure modes. For the EvoCode/Harbor setup, a publishable run should establish round completeness, clean Harbor exit, absence of known runtime/provider failures, sandbox cleanup, exact provenance, verifier isolation, and secret-free publishable artifacts.

## Verifier isolation

The source audit verifies that Harbor's `_prepare_step` calls `_reset_shared_step_verifier_dirs` when required, so previous grading artifacts are cleared before a later agent phase. The reference environment passed this check at Harbor SHA `99218a4611e3bd76e49ce3b5f977e8c8134ad3ac`.
