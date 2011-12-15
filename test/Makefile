
.PHONY: all
all: headers speak webui

.PHONY: headers
headers:
	python test_headers.py

.PHONY: speak
speak:
	PYTHONPATH=../ python -m redbot.speak

.PHONY: webui
webui: deploy
	python test_webui.py

.PHONY: deploy
deploy:
	cd deploy; make

.PHONY: lint
lint:
	PYTHONPATH=../ pylint-2.7 -i y \
	-d C0103,C0322,C0323,C0111,R0903,R0801,W0611,W0613 \
	redbot