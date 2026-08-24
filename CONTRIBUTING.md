# Contributing to NEXUS FIVE 3D ULTRA

Thanks for helping improve the project.

## Local setup

1. Install Python 3.11 or newer.
2. Create a virtual environment.
3. Install dependencies with `python -m pip install -r requirements.txt`.
4. Run `python CHECK_PROJECT.py`.
5. Launch with `python main.py`.

## Before opening a pull request

Run:

```bash
python CHECK_PROJECT.py
python -m compileall -q .
```

For changes to graphics or gameplay, test the affected mode in Panda3D and include a screenshot or short capture when possible.

## Repository hygiene

Do not commit:

- passwords, tokens, API keys, or webhooks
- virtual environments
- Python cache files
- local save files
- large raw art source files unless they are intentionally part of the project

Large binary assets should use Git LFS when they approach GitHub's normal Git limits.
