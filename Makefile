PROJECT = redbot

NPX=npx --cache .npx-cache -y
STANDARD=$(NPX) standard
WEBPACK=$(NPX) webpack-cli
CSSMIN=$(NPX) cssmin
SASS=$(NPX) sass
J2LINT=$(VENV)/j2lint

MODULES = src/node_modules
JS_ENTRIES = ./src/js/red_script.js ./src/js/red_request.js ./src/js/red_response.js ./src/js/red_response_multi.js
CSSFILES = redbot/assets/red_style.css $(MODULES)/google-code-prettify/src/prettify.css

ICONS = solid/check-circle solid/times-circle solid/question-circle solid/exclamation-circle solid/info-circle
ICON_FILES = $(foreach i, $(ICONS),$(MODULES)/@fortawesome/fontawesome-free/svgs/$(i).svg)

#############################################################################
## Tasks

.PHONY: clean
clean: clean_py
	rm -rf .npx-cache .pytest_cache throwaway fail_*.png test_summary.md *.log $(MODULES)

.PHONY: lint
lint: lint_py
	$(STANDARD) "src/js/*.js"
	$(J2LINT) redbot/formatter/templates/

.PHONY: typecheck
typecheck: typecheck_py

.PHONY: tidy
tidy: tidy_py
	$(STANDARD) --fix "src/js/*.js"


#############################################################################
## Tests


# Auto-discover test files
TEST_SOURCES = $(wildcard test/test_*.py)
TEST_TARGETS = $(patsubst test/%.py,%,$(TEST_SOURCES))

.PHONY: test
test: $(TEST_TARGETS) coverage i18n-check

# Generic rule for running tests
test_%: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python test/$@.py

# Specific rule for webui (needs dependencies)
.PHONY: test_webui
test_webui: venv
	$(VENV)/playwright install chromium
	@echo "Starting test server..."
	@PYTHONPATH=.:$(VENV) $(VENV)/python -u test/server.py > server.log 2>&1 & PID=$$!; \
	echo "Starting REDbot server..."; \
	PYTHONPATH=.:$(VENV) $(VENV)/python -u test/run_redbot.py > redbot.log 2>&1 & RPID=$$!; \
	trap "kill $$PID $$RPID; wait $$PID $$RPID; echo '--- Test Server Log ---'; cat server.log; rm server.log; echo '--- REDbot Server Log ---'; cat redbot.log; rm redbot.log" EXIT; \
	echo "Waiting for test server..."; \
	while ! nc -z localhost 8001; do sleep 0.1; done; \
	echo "Waiting for REDbot server..."; \
	while ! nc -z localhost 8000; do sleep 0.1; done; \
	PYTHONPATH=.:$(VENV) $(VENV)/python test/test_webui.py

.PHONY: coverage
coverage: venv
	PYTHONPATH=. $(VENV)/python test/coverage.py

#############################################################################
## i18n

.PHONY: i18n-extract
i18n-extract: venv
	PYTHONPATH=. $(VENV)/pybabel extract --omit-header --ignore-dirs="build dist .venv" -F tools/i18n/babel.cfg -o redbot/translations/messages.pot .

.PHONY: i18n-update
i18n-update: i18n-extract venv
	$(VENV)/pybabel update -i redbot/translations/messages.pot -d redbot/translations

.PHONY: i18n-autotranslate
i18n-autotranslate: venv
	$(VENV)/python -m tools.i18n.autotranslate --locale_dir redbot/translations --model $(or $(MODEL), 'mlx-community/aya-23-8B-4bit') #--rpm $(or $(RPM),10)

.PHONY: i18n-compile
i18n-compile: venv
	$(VENV)/pybabel compile -d redbot/translations

.PHONY: translations
translations: i18n-update i18n-compile

.PHONY: i18n-check
i18n-check: venv
	PYTHONPATH=. $(VENV)/python -m tools.i18n.check

.PHONY: i18n-init
i18n-init: venv
	@if [ -z "$(LOCALE)" ]; then echo "Usage: make init_locale LOCALE=xx"; exit 1; fi
	$(VENV)/pybabel init -i redbot/translations/messages.pot -d redbot/translations -l $(LOCALE)

#############################################################################
## Local test server / cli

.PHONY: server
server: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python -u redbot/daemon.py config.txt

.PHONY: test_server
test_server: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python -u test/server.py

.PHONY: cli
cli: venv
	PYTHONPATH=.:$(VENV) $(VENV)/python redbot/cli.py $(filter-out $@,$(MAKECMDGOALS))

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
