PYTHON=python3

.PHONY: all
all: unit webui

.PHONY: unit
unit:
	$(PYTHON) unit_tests.py

.PHONY: note_coverage
note_coverage:
	PYTHONPATH=../ $(PYTHON) note_coverage.py

.PHONY: header_coverage
header_coverage:
	PYTHONPATH=../ $(PYTHON) header_coverage.py registries/message-headers.xml

.PHONY: webui
webui: deploy
	$(PYTHON) test_webui.py

.PHONY: clean
clean:
	cd deploy; make clean-redbot

.PHONY: server
server:
	cd deploy; make server

.PHONY: lint
lint:
	PYTHONPATH=../ pylint redbot