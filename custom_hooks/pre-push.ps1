echo "Running pre-push tests!"
& .\env\Scripts\activate
echo "Activated venv"
python -m pytest -v
if ($LastExitCode -eq 0) {
    echo "Tests passed!"
} else {
    echo "Tests failed :("
    exit 1
}