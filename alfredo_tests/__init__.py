import yaml

# Read config
with open("alfredo_tests/src/tests.yaml") as _tf:
    TEST_CFG = yaml.safe_load(_tf)
