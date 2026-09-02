# Installation

Runsheet needs Python 3.14+ with Tkinter — on several platforms Tkinter is a separate package from Python itself, so it's called out below wherever that's the case.

## macOS (Homebrew)

```sh
brew install python@3.14 python-tk@3.14
```

## Windows (winget)

```sh
winget install --id Python.Python.3.14
```

The official python.org installer that winget uses bundles Tkinter already, so no separate package is needed.

## Debian / Ubuntu (apt)

```sh
sudo apt update
sudo apt install python3 python3-tk
```

## Fedora / RHEL / CentOS (dnf)

```sh
sudo dnf install python3 python3-tkinter
```

## Verify

```sh
python3 -c "import tkinter; print(tkinter.TkVersion)"
```

This should print a version number (e.g. `9.0`) with no errors.
