PYTHON=python3

.PHONY: all
all: unit speak webui

.PHONY: unit
unit:
	$(PYTHON) unit_tests.py

.PHONY: speak
speak:
	PYTHONPATH=../ $(PYTHON) -m redbot.speak

.PHONY: webui
webui: deploy
	$(PYTHON) test_webui.py

.PHONY: deploy
deploy:
	cd deploy; make

.PHONY: clean
clean:
	cd deploy; make clean-redbot

.PHONY: server
server:
	cd deploy; make server

.PHONY: lint
lint:
	PYTHONPATH=../ pylint -i y \
	-d C0103,C0322,C0323,C0111,R0903,R0801,W0611,W0613 \
	redbot