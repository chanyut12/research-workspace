"""Check that the Python running the scripts has the packages research-workbench needs."""
import importlib.util
import sys

REQUIRED = {"yaml": "pyyaml", "jsonschema": "jsonschema"}


def missing() -> list[str]:
    return [pkg for mod, pkg in REQUIRED.items() if importlib.util.find_spec(mod) is None]


def main() -> int:
    m = missing()
    if m:
        print(f"missing Python packages for {sys.executable}: {' '.join(m)}\n"
              f"install with: {sys.executable} -m pip install --user {' '.join(m)}\n"
              f"(Homebrew Python may also need --break-system-packages)")
        return 1
    print(f"OK: dependencies available for {sys.executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
