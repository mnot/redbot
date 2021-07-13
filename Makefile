NPX=npx --cache .npx-cache
STANDARD=$(NPX) standard
WEBPACK=$(NPX) webpack-cli
CSSMIN=$(NPX) cssmin
SASS=$(NPX) node-sass

WEBPACK_DEPS = node_modules/webpack node_modules/webpack-cli node_modules/exports-loader

MODULES = src/node_modules
JS_ENTRIES = ./src/js/red_script.js ./src/js/red_request.js ./src/js/red_response.js ./src/js/red_response_multi.js
CSSFILES = redbot/assets/red_style.css $(MODULES)/google-code-prettify/src/prettify.css

ICONS = solid/check-circle solid/times-circle solid/question-circle solid/exclamation-circle solid/info-circle brands/twitter
ICON_FILES = $(foreach i, $(ICONS),$(MODULES)/@fortawesome/fontawesome-free/svgs/$(i).svg)

#############################################################################
## Tasks

.PHONY: test
test: typecheck unit_test webui_test

.PHONY: clean
clean:
	find . -d -type d -name __pycache__ -exec rm -rf {} \;
	rm -rf build dist MANIFEST redbot.egg-info package-lock.json node_modules .venv .npx-cache .mypy_cache *.log

.PHONY: tidy
tidy: venv node_modules/standard
	$(VENV)/black redbot bin/*
	$(STANDARD) --fix src/js/*.js

.PHONY: lint
lint: venv node_modules/standard
	PYTHONPATH=$(VENV) $(VENV)/pylint --output-format=colorized --rcfile=test/pylintrc \
	  redbot bin/redbot_daemon.py bin/redbot_cgi.py bin/redbot_cli
	$(STANDARD) src/js/*.js

.PHONY: typecheck
typecheck: venv
	PYTHONPATH=$(VENV) $(VENV)/python -m mypy --config-file=test/mypy.ini \
	  redbot \
	  bin/redbot_daemon.py \
	  bin/redbot_cgi.py \
	  bin/redbot_cli

.PHONY: syntax
syntax: venv
	PYTHONPATH=$(VENV) $(VENV)/python redbot/syntax/__init__.py


#############################################################################
## Coverage and Tests

.PHONY: note_coverage
note_coverage: venv
	PYTHONPATH=$(VENV) $(VENV)/python test/note_coverage.py

.PHONY: header_coverage
header_coverage: venv
	PYTHONPATH=$(VENV) $(VENV)/python test/header_coverage.py test/registries/message-headers.xml

.PHONY: webui_test
webui_test: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python test/test_webui.py

.PHONY: unit_test
unit_test: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python test/unit_tests.py

#############################################################################
## Local test server

.PHONY: server
server: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python -u bin/redbot_daemon.py config.txt


#############################################################################
## Docker

.PHONY: docker-image
docker-image:
	docker build -t redbot .

.PHONY: docker
docker: docker-image
	docker run --rm --name redbot -p 8000:8000 redbot

#############################################################################
## Distribution

build: clean venv
	$(VENV)/python -m build

.PHONY: upload
upload: build typecheck test
	git tag redbot-$(version)
	git push
	git push --tags origin
	$(VENV)/python -m twine upload dist/*

#############################################################################
## Create new headers

redbot/message/headers/%.py:
	cp redbot/message/headers/_header.tpl $@
	sed -i '' -e "s/SHORT_NAME/$*/g" $@

#############################################################################
## Assets

.PHONY: redbot/assets
redbot/assets: redbot/assets/script.js redbot/assets/prettify.js redbot/assets/style.css redbot/assets/icons

redbot/assets/prettify.js: $(WEBPACK_DEPS)
	$(WEBPACK) --entry ./$(MODULES)/google-code-prettify/src/prettify.js --config ./src/js/webpack.config.js --mode production --output-path . --output-filename $@

redbot/assets/script.js: src/js/*.js $(WEBPACK_DEPS)
	$(WEBPACK) $(JS_ENTRIES) --config ./src/js/webpack.config.js --mode production --output-path . --output-filename $@

redbot/assets/red_style.css: src/scss/*.scss
	$(SASS) src/scss/red_style.scss $@

redbot/assets/style.css: $(CSSFILES) node_modules/cssmin
	cat $(CSSFILES) | $(CSSMIN) > $@

redbot/assets/icons: $(ICON_FILES)
	mkdir -p $@
	cp $(ICON_FILES) $@/

.PHONY: clean-assets
clean-assets:
	rm -rf redbot/assets/*.js redbot/assets/*.map redbot/assets/*.css redbot/assets/icons

#############################################################################
## NPM dependencies

node_modules/%:
	npm i $(notdir $@)


include Makefile.venv
