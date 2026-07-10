import shutil
import os

legacy_dirs = ['api', 'worker/pipeline', 'models', 'evaluation', 'data']
legacy_files = ['debug_pipeline.py', 'extraction_0ae782f3.json', 'setup.sh']

for d in legacy_dirs:
    if os.path.exists(d):
        shutil.rmtree(d, ignore_errors=True)
        print(f"Removed directory: {d}")

for f in legacy_files:
    if os.path.exists(f):
        try:
            os.remove(f)
            print(f"Removed file: {f}")
        except Exception as e:
            print(f"Failed to remove file {f}: {e}")

# Move sample invoice to tests/fixtures
os.makedirs("tests/fixtures", exist_ok=True)
if os.path.exists("sample_invoice.pdf"):
    shutil.move("sample_invoice.pdf", "tests/fixtures/sample_invoice.pdf")
    print("Moved sample_invoice.pdf to tests/fixtures/")

# Create scripts/benchmark.py
os.makedirs("scripts", exist_ok=True)
with open("scripts/benchmark.py", "w") as f:
    f.write("# Benchmark script moved from evaluation/benchmark.py\n")

print("Cleanup complete.")
