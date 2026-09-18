# AGENTS.md

Instructions for agents to build and maintain the Duplicate Size Scanner application.

## Product requirements

- Build a Python 3.14+ PySide6 desktop application for Windows and Linux.
- Find files with equal byte sizes. Present them as possible duplicates.
- Support comparison between two folders and repeated-size searches within a single
  folder.

## Scan behavior

- Let the user select two different folder locations or enable a single location mode.
- In two-location mode, report a size when each location contains at least one
  eligible file of that size. Include every eligible file of that size from
  both locations.
- In single-location mode, report a size when Location 1 contains at least two
  eligible files of that size.
- Let the user include or exclude subfolders independently for each location selector.
- Accept comma-separated extension exclusions. Match them without case
  sensitivity, accept optional dots or wildcard markers and support compound
  extensions such as `.tar.gz`.
- Let the user set an integer minimum size in decimal megabytes, where
  `1 MB = 1,000,000 bytes`.
- Require each enabled root to exist and be a directory. Reject equal or nested
  roots in two-location mode.
- Exclude zero-byte files, symbolic links and non-regular file-system entries.
- Fail the scan when an enabled root directory cannot be read. Skip unreadable folders or entries and report warnings to the user.
- Sort result list from largest file size to smallest.
- Run scanning on a worker thread so the GUI can stay responsive. Report scan status without blocking the interface.

## Results and file actions

- Show each result's full location, filename and formatted size, in that order.
- Provide a right-click menu with actions to open, rename or delete an individual file (delete uses the OS trash can).
- Validate that a result path still identifies a regular file before each file
  action.
- Keep rename operations in the same folder. Reject invalid names.
- Require confirmation before moving a file to Trash.
- Pass file paths as arguments without shell interpretation.
- Update or remove result groups after a successful rename or delete operation.

## Settings

- Save user-entered paths and scan options between sessions in an .ini file.
- Use the Qt generic user configuration location followed by
  `DuplicateSizeScanner/settings.ini`.
- Use `~/.config/DuplicateSizeScanner/settings.ini` if Qt does not provide a
  generic configuration location.
- Preserve path text exactly as the user entered it.
- Use safe defaults when the settings file is missing or invalid.
- Report write failures without terminating the application.

## Desktop GUI

- Use the `qt-material` theme `dark_amber.xml`.
- Use the provided `src/ui_style.py` as the source of truth for recurring style elements. Do not duplicate color values in window code.
- Use a filled accent style for primary actions and an outlined accent style
  for secondary actions.
- Give interactive buttons explicit hover and pressed feedback.
- Add recurring style patterns to `src/ui_style.py` before using them in window
  code.

## Platform and executable behavior

- Implement and test platform behavior for both Windows and Linux.
- Use native file-opening APIs.
- Provide separate Windows and Linux PyInstaller commands because builds are
  platform-specific.
- Include `qt_material` data in each PyInstaller build.

## Project files and documentation

- Put runtime dependencies in `requirements.txt`.
- Put testing, formatting, linting and executable-build tools in
  `requirements-dev.txt`. Include `requirements.txt` from that file.
- Configure Ruff, formatting, docstring and pytest behavior in
  `pyproject.toml`.

## Tests and continuous integration

- Test scan matching, filtering, validation, warnings, settings persistence,
  safe file actions and user-interface behavior.
- Configure Qt widget tests to use the offscreen platform in automation.
- Run Ruff lint and format checks in continuous integration.
- Run pytest on both Linux and Windows in continuous integration.

## Development checks

- Prefer tools from the local `.venv` when it exists.
- After Python code or test changes, run:
    - `.venv/bin/ruff check --fix`
    - `.venv/bin/ruff format`
    - `.venv/bin/pytest`
- These checks are not required for documentation-only changes unless the
  documentation changes a command or configuration example.
- Treat `pyproject.toml` as the source of truth for tool configuration.

## Code review guidelines

- Do not report formatting or import-order findings, Ruff handles those.
- Prioritize correctness, edge cases, error handling, file-system safety,
  maintainability, types and public API behavior.

## Python standards

- Python 3.14 or newer is required.
- Prefer clear code over using new language features for their own sake.
- Prefer f-strings over `%` or `.format()`, except for lazy logging calls.
- Use dataclasses when they make data structures clearer.
- Use pattern matching when it simplifies branching.
- Use assignment expressions only when they improve clarity.

## Typing and documentation

- Add type hints to all public functions and methods, public attributes,
  dataclass fields and variables whose types are not clear from context.
- Add docstrings to public modules, packages, classes, functions and methods.
  A name that starts with `_` is considered private.
- Do not require docstrings for `__init__`, magic methods or nested classes.
- Use Google-style docstrings.
- Write comments that explain why code behaves as it does, not comments that
  restate the code.

## Writing style

- Follow ASD-STE100 Simplified Technical English.
- Use concise American English and sentence case in documentation, comments
  and user-facing text.
- Use second person for user-facing instructions when it improves clarity.
- Use objective and inclusive language that is clear to non-native English
  speakers.
- In Markdown, use backticks for paths, filenames, variables, field entries
  and commands.
- Avoid unnecessary abbreviations. Established technical terms and units such
  as API, Qt, MB, POSIX etc. are acceptable.

## Error handling

- Use the most specific exception type available and keep `try` blocks small.
- Avoid broad exception catches inside application logic.
- Allow `except Exception` at process and worker boundaries only when the code
  logs the failure and reports a safe user-facing error.
- When re-raising with context, use `raise ... from err`.

## Return statement spacing

Add one blank line before a final `return` when it separates the result from
the preceding processing.

Do not add a blank line before short guard-clause returns.

Preferred:

```python
if value is None:
    return None

result = process(value)

return result
```

## Docstring spacing

Add one blank line after docstrings on public methods.

```python
class SomePublicClass:
    """Docstring text."""

    someVar: None
```
