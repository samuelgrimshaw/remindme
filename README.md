# RemindMe

A command-line calendar manager written in Python that stores events locally and syncs them to iCloud Calendar using CalDAV.

I built this to keep track of university deadlines, lectures and work shifts, with everything showing up on my calendar via iCloud.

## Features

- Add, edit, view and delete events with simple terminal commands
- One-off and recurring events (daily, weekly, monthly)
- Upcoming view that groups events into the next 7, 30 and 365 days
- iCloud sync over CalDAV
  - New events are uploaded with a reminder 1 hour before
  - Edited events are updated in place, matched by their UID
  - Deleted events are queued locally and removed from iCloud on the next sync
- Input validation for dates and times
- Local JSON storage, so it works offline until you sync

## Requirements

- Python 3.10 or newer 
- An iCloud account with an [app-specific password](https://support.apple.com/en-gb/102654)

> **Note:** You must generate an app-specific password at [account.apple.com](https://account.apple.com) and use that when syncing.

## Installation

Clone the repository:

```bash
git clone https://github.com/Snowiezz/remindme.git
cd remindme
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

### Setting up the calendar

RemindMe syncs into a calendar called **`RemindMe`**. Before your first sync, create it in the Calendar app (or at [icloud.com/calendar](https://www.icloud.com/calendar)) under your iCloud account, using exactly that name.

## Usage

Dates are written as `DDMMYY` and times as `HHMM` in 24-hour format.

| Command | What it does |
| --- | --- |
| `python main.py add <desc> <date> <time>` | Add an event |
| `python main.py list` | Show all events |
| `python main.py upcoming` | Show events in the next 7 / 30 / 365 days |
| `python main.py edit <id> <field> <value>` | Change an event's `date`, `time`, `mod` or `desc` |
| `python main.py delete <id>` | Delete an event |
| `python main.py sync` | Sync everything to iCloud |

### Examples

Add a one-off deadline with a module code:

```bash
python main.py add "Essay deadline" 041126 0900 --mod COMP101
```

Add a lecture that repeats every week:

```bash
python main.py add "Algorithms lecture" 031126 1400 --mod COMP202 --repeat weekly
```

Move event 2 to a new time:

```bash
python main.py edit 2 time 1500
```

Sync to iCloud (enter your Apple ID email and app-specific password):

```bash
python main.py sync
```

Run `python main.py --help` for every option.

## How syncs work

Each event gets a UID the first time it's synced, and that UID is stored in `events.json`. On every sync RemindMe fetches the events already in the `RemindMeNEW` calendar and compares UIDs:

- **Not on iCloud yet**: the event is uploaded.
- **Already on iCloud and edited locally**: the remote copy is updated in place.
- **Deleted locally**: the UID was saved to `deleted_events.json` when you deleted it, so the remote copy is removed and the queue is cleared.

Times default to a 30 minute block. Functionality to change these blocks will be added soon.

## How to run tests

The tests use `pytest` and write to a temporary folder, so your real `events.json` is never touched.

```bash
pip install pytest
pytest
```

They cover date and time parsing, adding events, and saving events to file. More to come soon.

## Project structure

```
main.py              # the whole app: CLI commands, event handling and iCloud sync
tests/test_main.py   # pytest tests
requirements.txt     # dependencies (caldav, icalendar)
events.json          # saved events (created automatically) (ignored)
deleted_events.json  # UIDs waiting to be deleted from iCloud (ignored)
```

## To do list

- Store credentials in the macOS Keychain instead of asking for them on every sync
- Two-way sync, so events added on iCloud are pulled back down
- Let the user choose event length, reminder time and time zone
- Include more tests
