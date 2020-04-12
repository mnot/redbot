PYTHON=python3
PYTHONPATH=./
SASS=sassc

MODULES = src/node_modules
JS_ENTRIES = src/js/red_script.js src/js/red_request.js src/js/red_response.js src/js/red_response_multi.js
CSSFILES = redbot/assets/red_style.css $(MODULES)/google-code-prettify/src/prettify.css


.PHONY: test
test: typecheck unit_test webui_test

.PHONY: clean
clean: clean-deploy
	find . -d -type d -name __pycache__ -exec rm -rf {} \;
	rm -rf build dist MANIFEST redbot.egg-info *.log

.PHONY: tidy
tidy:
	black redbot bin/*
	standard --fix src/js/*.js

.PHONY: lint
lint:
	PYTHONPATH=$(PYTHONPATH) pylint --output-format=colorized --rcfile=test/pylintrc \
	  redbot bin/redbot_daemon.py bin/redbot_cgi.py bin/redbot_cli
	standard src/js/*.js

.PHONY: typecheck
typecheck:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mypy --config-file=test/mypy.ini \
	  redbot \
	  bin/redbot_daemon.py \
	  bin/redbot_cgi.py \
	  bin/redbot_cli

.PHONY: syntax
syntax:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) redbot/syntax/__init__.py

## Coverage and Tests

.PHONY: note_coverage
note_coverage:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) test/note_coverage.py

.PHONY: header_coverage
header_coverage:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) test/header_coverage.py test/registries/message-headers.xml

.PHONY: webui_test
webui_test: deploy
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) test/test_webui.py

.PHONY: unit_test
unit_test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) test/unit_tests.py

## Deploy and Server

.PHONY: server
server: clean-deploy deploy
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -u deploy/redbot_daemon.py config.txt

.PHONY: deploy
deploy: clean-deploy
	mkdir deploy
	cp -p bin/redbot_daemon.py deploy/
	chmod a+x deploy/redbot_daemon.py

.PHONY: clean-deploy
clean-deploy:
	rm -rf deploy

## Docker

.PHONY: docker-image
docker-image:
	docker build -t redbot .

.PHONY: docker
docker: docker-image
	docker run -p 8000:8000 redbot

## Distribution

.PHONY: dist
dist: clean typecheck test
	git tag redbot-$(version)
	git push
	git push --tags origin
	$(PYTHON) setup.py sdist
	$(PYTHON) -m twine upload dist/*

## New headers

redbot/message/headers/%.py:
	cp redbot/message/headers/_header.tpl $@
	sed -i '' -e "s/SHORT_NAME/$*/g" $@

## assets

.PHONY: redbot/assets
redbot/assets: redbot/assets/script.js redbot/assets/prettify.js redbot/assets/style.css redbot/assets/webfonts

redbot/assets/prettify.js:
	webpack-cli --entry ./$(MODULES)/google-code-prettify/src/prettify.js --config src/js/webpack.config.js --mode production --output $@

redbot/assets/script.js: src/js/*.js
	webpack-cli $(JS_ENTRIES) --config src/js/webpack.config.js --mode production --output $@

redbot/assets/red_style.css: src/scss/*.scss
	$(SASS) src/scss/red_style.scss $@

redbot/assets/style.css: $(CSSFILES)
	cat $(CSSFILES) | cssmin > $@

redbot/assets/webfonts:
	cp -R $(MODULES)/font-awesome/fonts $@

.PHONY: clean-assets
clean-assets:
	rm -rf redbot/assets/*.js redbot/assets/*.map redbot/assets/*.css redbot/assets/webfonts
