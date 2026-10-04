import runpy, sys
from pathlib import Path

def _find_repo_root():
    here = Path(__file__).resolve()
    # src/analbot/__main__.py -> parents[3] is repo root
    return here.parents[3] if len(here.parents) >= 4 else here.parents[-1]

def main():
    repo_root = _find_repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    entry_rel = 'bot.py'
    if not entry_rel:
        print("No entrypoint detected.", file=sys.stderr)
        sys.exit(2)
    target = repo_root / entry_rel
    if not target.exists():
        print(f"Entrypoint not found: {target}", file=sys.stderr)
        sys.exit(2)
    runpy.run_path(str(target), run_name="__main__")

if __name__ == "__main__":
    main()
