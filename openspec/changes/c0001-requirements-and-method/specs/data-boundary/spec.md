## ADDED Requirements

### Requirement: Clean-room sources
The repository SHALL be derived only from the two public write-ups of the system; no employer repository, cluster alias, internal service name, customer name, chat domain or account number may appear in any file.

#### Scenario: Leak scan
- **WHEN** `python3 tools/check_rules.py` runs
- **THEN** it prints `check_rules: OK` and exits 0

### Requirement: Private patterns stay private
Private leak patterns SHALL live in `.leak_patterns.local`, which is gitignored, so the repository never contains the words it guards against.

#### Scenario: Pattern file not tracked
- **WHEN** `git ls-files` runs
- **THEN** `.leak_patterns.local` is not listed

### Requirement: The scan fails loudly
The scan SHALL exit non-zero and name file and line for every hit, and SHALL fail if a required document is missing.

#### Scenario: Planted leak
- **WHEN** a file contains a string matching a pattern
- **THEN** exit code is 1 and the output contains `leak pattern in <file>:<line>`
