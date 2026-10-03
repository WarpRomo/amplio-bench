# Release checklist

Before publishing a benchmark harness release:

1. Unit tests pass under the supported Python version.
2. Python sources compile.
3. Shell helpers pass `bash -n`.
4. The retained reference trajectory re-analyzes to the expected metrics.
5. The retained reference run passes the validity audit.
6. Provenance regeneration succeeds.
7. A fresh live integration smoke completes end to end.
8. No sandbox remains after the live smoke.
9. Publishable files pass the secret scan.
10. Only the explicit public-file allowlist is staged.
11. Review `git diff --cached` before pushing.

Do not use an integration smoke's task score as a benchmark result; its purpose is
to validate plumbing.
