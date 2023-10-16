PROJECT = redbot

NPX=npx --cache .npx-cache -y
STANDARD=$(NPX) standard
WEBPACK=$(NPX) webpack-cli
CSSMIN=$(NPX) cssmin
SASS=$(NPX) node-sass

MODULES = src/node_modules
JS_ENTRIES = ./src/js/red_script.js ./src/js/red_request.js ./src/js/red_response.js ./src/js/red_response_multi.js
CSSFILES = redbot/assets/red_style.css $(MODULES)/google-code-prettify/src/prettify.css

ICONS = solid/check-circle solid/times-circle solid/question-circle solid/exclamation-circle solid/info-circle
ICON_FILES = $(foreach i, $(ICONS),$(MODULES)/@fortawesome/fontawesome-free/svgs/$(i).svg)

#############################################################################
## Tasks

.PHONY: clean
clean: clean_py
	rm -rf .npx-cache throwaway

.PHONY: lint
lint: lint_py
	$(STANDARD) "src/js/*.js"

.PHONY: typecheck
typecheck: typecheck_py

.PHONY: tidy
tidy: tidy_py
	$(STANDARD) --fix "src/js/*.js"


#############################################################################
## Tests

.PHONY: test
test: webui_test

.PHONY: webui_test
webui_test: venv
	$(VENV)/playwright install chromium
	PYTHONPATH=.:$(VENV) $(VENV)/python test/test_webui.py


#############################################################################
## Local test server / cli

.PHONY: server
server: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python -u redbot/daemon.py config.txt

.PHONY: cli
cli: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python redbot/cli.py $(filter-out $@,$(MAKECMDGOALS))

#############################################################################
## Docker

.PHONY: docker-image
docker-image:
	docker build -t redbot .

.PHONY: docker
docker: docker-image
	docker run --rm --name redbot -p 8000:8000 redbot

.PHONY: docker-cli
docker-cli: docker-image
	docker run --rm --name redbot redbot redbot/cli.py https://redbot.org/

#############################################################################
## Assets

.PHONY: redbot/assets
redbot/assets: redbot/assets/script.js redbot/assets/prettify.js redbot/assets/style.css redbot/assets/icons

redbot/assets/prettify.js: $(MODULES)
	$(WEBPACK) --entry ./$(MODULES)/google-code-prettify/src/prettify.js --config ./src/js/webpack.config.js --mode production --output-path . --output-filename $@

redbot/assets/script.js: $(MODULES) src/js/*.js
	$(WEBPACK) $(JS_ENTRIES) --config ./src/js/webpack.config.js --mode production --output-path . --output-filename $@

redbot/assets/red_style.css: src/scss/*.scss
	$(SASS) src/scss/red_style.scss $@

redbot/assets/style.css: $(MODULES) $(CSSFILES)
	cat $(CSSFILES) | $(CSSMIN) > $@

redbot/assets/icons: $(MODULES)
	mkdir -p $@
	cp $(ICON_FILES) $@/

.PHONY: clean-assets
clean-assets:
	rm -rf redbot/assets/*.js redbot/assets/*.map redbot/assets/*.css redbot/assets/icons

$(MODULES):
	npm i --prefix=./src/


include Makefile.pyproject
