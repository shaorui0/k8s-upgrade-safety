# c0001 acceptance evidence

## 3.1 unit tests for the scan
```
$ python3 -m unittest discover -s tools -v 2>&1 | grep -v '^FAIL'
test_clean_tree_passes (test_check_rules.CheckRulesTest.test_clean_tree_passes) ... ok
test_main_exit_code (test_check_rules.CheckRulesTest.test_main_exit_code) ... ok
test_missing_required_doc_fails (test_check_rules.CheckRulesTest.test_missing_required_doc_fails) ... ok
test_planted_private_leak_fails_with_file_and_line (test_check_rules.CheckRulesTest.test_planted_private_leak_fails_with_file_and_line) ... ok
test_public_patterns (test_check_rules.CheckRulesTest.test_public_patterns) ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.083s

OK
exit=0
```

## 3.2 leak scan, pattern file untracked, independent grep with the same private patterns
```
$ python3 tools/check_rules.py; git ls-files | grep -c leak_patterns; grep -rniE -f .leak_patterns.local --exclude-dir=.git --exclude=.leak_patterns.local . | wc -l
check_rules: OK
0
       0
exit=0
```

## 3.3 openspec validate
```
$ openspec validate c0001-requirements-and-method
Change 'c0001-requirements-and-method' is valid
exit=0
```

## docs present: mermaid blocks, apiserver gate section, requirement rows
```
$ grep -c '^```mermaid' docs/METHOD.md; grep -n 'The apiserver is the gate' docs/METHOD.md; grep -c '^| R' docs/REQUIREMENTS.md
1
89:#### The apiserver is the gate
15
exit=0
```
