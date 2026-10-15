.PHONY: test serve demo demo-large citizen-add citizens mine tally status clean

PYTHON ?= python

test:
	pytest -v

serve:
	$(PYTHON) -m openballot.cli serve --port 8000 --difficulty 1

demo:
	$(PYTHON) scripts/setup_election.py --count 5

demo-large:
	$(PYTHON) scripts/setup_election.py --count 10

citizen-add:
	$(PYTHON) -m openballot.cli citizen-create --name "Marcus Aurelius" --district "Capitol District"

citizens:
	$(PYTHON) -m openballot.cli citizen-list

mine:
	$(PYTHON) -m openballot.cli mine

tally:
	$(PYTHON) -m openballot.cli tally --proposal PROP-2026-01

status:
	$(PYTHON) -m openballot.cli status

clean:
	$(PYTHON) -c "import shutil, glob, os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True) + ['.pytest_cache']]"
