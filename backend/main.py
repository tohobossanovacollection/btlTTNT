import os
import sys
from pathlib import Path


def _using_virtualenv() -> bool:
    return sys.prefix != sys.base_prefix or bool(os.environ.get("VIRTUAL_ENV"))


def _project_venv_python() -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    return Path(__file__).resolve().parent / ".venv" / scripts_dir / executable


def _ensure_project_python() -> None:
    if _using_virtualenv():
        return

    venv_python = _project_venv_python()
    if not venv_python.exists():
        return

    current_python = Path(sys.executable).resolve()
    if current_python == venv_python.resolve():
        return

    os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])


def main() -> None:
    _ensure_project_python()

    try:
        import uvicorn
        from dotenv import load_dotenv
    except ModuleNotFoundError as exc:
        missing = exc.name or "required package"
        raise SystemExit(
            f"Missing dependency '{missing}'. Run "
            r".\.venv\Scripts\python.exe -m pip install -r requirements.txt, then run python main.py."
        ) from exc

    load_dotenv(dotenv_path=".env")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()


# Backend test URL:
# http://127.0.0.1:8000/docs#/Chat/chat_api_v1_chat__post
