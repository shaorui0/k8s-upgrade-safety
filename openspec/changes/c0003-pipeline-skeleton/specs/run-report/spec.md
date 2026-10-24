## ADDED Requirements

### Requirement: HTML report per run
Every command SHALL write `runs/<run_id>/report.html` containing the decision, the step table with status, the check criteria before and after, the plan, the diff against baseline, rollback advice when present and the log.

#### Scenario: Report exists
- **WHEN** any command finishes, including failed or awaiting approval
- **THEN** report.html exists and escapes all data it embeds
