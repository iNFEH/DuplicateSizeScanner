# Build Instructions

PyInstaller builds are platform-specific. Build the Windows executable on
Windows and the Linux executable on Linux. Run all commands from the project
root folder. Python 3.14 or newer is required.

## Windows (PowerShell)

Create the virtual environment and install the dependencies if needed:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements-dev.txt
```

Build one windowed executable:

```powershell
py -m PyInstaller --noconfirm --clean --onefile --windowed --name DuplicateSizeScanner --collect-data qt_material src\main.py
```

The executable is created at:

```text
dist\DuplicateSizeScanner.exe
```

## Linux

Create the virtual environment and install the dependencies if needed:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

Build one executable:

```bash
python3 -m PyInstaller --noconfirm --clean --onefile --name DuplicateSizeScanner --collect-data qt_material src/main.py
```

The executable is created at:

```text
dist/DuplicateSizeScanner
```
