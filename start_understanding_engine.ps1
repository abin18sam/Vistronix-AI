$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$service = $root
$python = Join-Path $root ".venv\Scripts\python.exe"

Set-Location $service
if (-not (Test-Path $python)) {
	throw "Virtual environment not found at $python. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
