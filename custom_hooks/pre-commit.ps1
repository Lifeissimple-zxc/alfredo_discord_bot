pwd
& .\env\Scripts\activate
echo "Running pre-commit tests!"
python -m pytest -v
