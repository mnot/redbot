
.PHONY: all
all: headers webui

.PHONY: headers
headers:
	python test_headers.py

.PHONY: webui
webui: deploy
	python test_webui.py

.PHONY: deploy
deploy:
	cd deploy; make	