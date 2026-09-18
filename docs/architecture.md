# Architecture

Duplicate Size Scanner uses a small layered desktop architecture. The GUI coordinates application services while scanning logic and file operations remain separate from the GUI.

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| `src/main.py` | Configures Qt and some basic logging, applies the theme, creates the main window and starts the event loop. |
| `src/ui.py` | Builds the interface which handles user input, manages the scan worker and displays results and errors. |
| `src/scanner.py` | Traverses paths, filters files and groups files by file size. |
| `src/settings.py` | Loads and saves user-specific application settings in a `.ini` file. |
| `src/file_actions.py` | Validates result paths and performs OS native open, rename and delete operations. |
| `src/ui_style.py` | Defines shared palette tokens and recurring Qt stylesheet builders. |

`src/ui.py` is the composition layer. It depends on the other application
modules, but the scanner does not depend on Qt and can be used and tested independently.

## Module map

```mermaid
flowchart LR
  MAIN["main.py - app startup"]
  UI["ui.py - GUI"]
  SCANNER["scanner.py - scanning service"]
  SETTINGS["settings.py - user settings"]
  ACTIONS["file_actions.py - file operations"]
  STYLE["ui_style.py - shared styles"]

  MAIN --> UI
  UI --> SCANNER
  UI --> SETTINGS
  UI --> ACTIONS
  UI --> STYLE
```

## Scan lifecycle

The scanner runs synchronously inside a worker object on a `QThread`. Qt
signals transfer status, warnings, results and failures back to the GUI thread.

```mermaid
sequenceDiagram
  actor User
  participant UI as GUI thread
  participant Settings
  participant Thread as QThread
  participant Worker as Scan worker
  participant Scanner

  User->>UI: Select Search
  UI->>UI: Validate required fields and build ScanRequest
  UI->>Settings: Save scan settings
  UI->>UI: Clear results and disable controls
  UI->>Thread: Start worker thread
  Thread->>Worker: Invoke run()
  Worker->>Scanner: Find matching file sizes

  loop Directory traversal
    Scanner-->>Worker: Invoke status or warning callback
    Worker-->>UI: Emit queued Qt signal
    UI->>UI: Update progress or warning state
  end

  alt Scan succeeds
    Scanner-->>Worker: Return ScanResult
    Worker-->>UI: Emit completion signal
    UI->>UI: Populate result tree
  else Scan fails
    Worker-->>UI: Emit failure signal
    UI->>UI: Display error
  end

  Worker-->>Thread: Emit finished signal
  Thread-->>UI: Emit thread finished signal
  UI->>UI: Re-enable controls
```
