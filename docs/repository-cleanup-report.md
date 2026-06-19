# Repository Cleanup Report

Date: 2026-06-18

## Scope

This cleanup reviewed repository hygiene for the MoniBox / HSC-RAG-DE reproduction
workspace without changing RAG, API, CLI, or experiment business logic.

## Removed Files

- Removed root `.env`.

The following local generated directories/files were found but were not bulk-deleted
because the workspace instructions prohibit batch deletion of files/directories:

- `.uv-cache` (`6` files, `3` directories observed)
- `frontend/node_modules` (`2379` files, `616` directories observed)
- `frontend/dist` (`3` files, `1` directory observed)
- `frontend/.npm-cache` (`0` files, `2` directories observed)
- `build/runtime_logs` (`1` file observed)
- Python `__pycache__` / `.pyc` files generated under source and test packages

These should be manually removed before packaging or publishing a clean working tree.

## Gitignore Updates

Updated `.gitignore` to cover private/generated paths:

- `.env`
- `.env.*`
- `.uv-cache/`
- `frontend/node_modules/`
- `frontend/dist/`
- `frontend/.npm-cache/`
- `build/runtime_logs/`
- `__pycache__/`
- `*.pyc`

The previous broad `build/` ignore rule was narrowed to `build/runtime_logs/` so
valid experiment assets such as `build/rag.db` and `build/runtime_pack.json` are not
silently hidden. They are currently visible as untracked files and need a project
decision: commit them as reproducibility assets or document them as generated outputs.

## Environment Template

Updated `.env.example` to contain placeholders only:

- `DEEPSEEK_API_KEY=<your_deepseek_api_key>`
- optional `HF_TOKEN=<your_huggingface_token>`
- optional runtime profile/path placeholders

No real key is included in `.env.example`.

## Tests Added / Updated

Added `tests/test_no_private_files.py` to verify:

- root `.env` is absent;
- private/cache paths are not tracked or unignored commit candidates;
- `.env.example` contains placeholders only;
- tracked text files do not contain obvious API key / token / secret patterns.

Updated old tests to match the current repository shape:

- `tests/test_runtime_config.py`: removed dependency on deleted private helper
  `_resolve_profile_path` and verified current profile loading behavior.
- `tests/test_cross_platform_dependencies.py`: read `pyproject.toml` as UTF-8 on
  Windows and updated dependency assertions to match the current dependency layout.

## Pytest Status

Final command:

```powershell
$env:PYTHONPATH = "D:\projects\monibox-Y\monibox\.venv\Lib\site-packages"; python -m pytest
```

Result:

```text
13 passed in 0.63s
```

Notes:

- `python -m pytest` with the system interpreter initially failed because the system
  Python had pytest but not project runtime dependencies.
- `.venv\Scripts\python.exe -m pytest` initially failed because the virtualenv had
  runtime dependencies but not pytest.
- The final run used system pytest with `.venv` site-packages on `PYTHONPATH` and
  passed without installing new dependencies.

## Manual Follow-up

- Manually remove the generated directories listed above if a physically clean
  workspace is required. This was not automated because batch deletion is forbidden.
- Decide whether `build/rag.db` and `build/runtime_pack.json` are committed
  reproducibility assets or generated artifacts.
- Consider installing the existing dev extra in `.venv` so future test runs can use
  `.venv\Scripts\python.exe -m pytest` directly.
