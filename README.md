# Description

This script can be used to add users in [eLabFTW](https://github.com/elabftw/elabftw) to teams and groups. Users, teams and groups must already exist in your elabftw instance.

## Prerequisites

- Python >= 3.10.x
- pip

## Usage

Clone repository and create virtual environment

```
python -m venv .venv
```

Activate virtual environment

Windows:
```
./.venv/bin/activate
```

Linux/macOS:
```
source .venv/bin/activate
```

Install requirements

```
pip install -r requirements.txt
```

Add your `ELAB_API_HOST_URL` and `ELAB_API_KEY` to `.env.example` and rename the example file to `.env`

Fill out the example Excel sheet `userlist_example.xlsx` and rename the example Excel sheet to `userlist.xlsx`. User with email must exist in eLabFTW. Also teams and groups must already be created in your instance.

Run the script in your code editor (e.g. VS Code) or via Terminal:

```
python -m teamupload_script.py
```
