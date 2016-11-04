PYTHON=python3
PYTHONPATH=./

BOWER = src/bower_components
JSFILES = $(BOWER)/jquery/dist/jquery.js $(BOWER)/jquery-hoverIntent/jquery.hoverIntent.js $(BOWER)/google-code-prettify/src/prettify.js src/red_script.js src/red_popup.js src/red_req_headers.js 
CSSFILES = share/red_style.css $(BOWER)/google-code-prettify/src/prettify.css


.PHONY: test
test: typecheck unit_test webui_test

.PHONY: clean
clean: clean-deploy
	find . -d -type d -name __pycache__ -exec rm -rf {} \;
	rm -rf build dist MANIFEST redbot.egg-info ghostdriver.log

.PHONY: lint
lint:
	PYTHONPATH=$(PYTHONPATH) pylint --rcfile=test/pylintrc redbot

.PHONY: typecheck
typecheck:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mypy --config-file=test/mypy.ini redbot

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
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) bin/webui.py 8080 share/

.PHONY: deploy
deploy: clean-deploy
	mkdir deploy
	cp -p bin/webui.py deploy/
	sed -i=.old '/DEBUG_CONTROL/s/False/True/g' deploy/webui.py
	chmod a+x deploy/webui.py

.PHONY: clean-deploy
clean-deploy:
	rm -rf deploy

## Snapshot

.PHONY: snapshot
snapshot:
#	git push
	$(PYTHON) setup.py egg_info -b .dev`git log -1 --pretty=format:%h` sdist # upload

## New headers

redbot/message/headers/%.py:
	cp redbot/message/headers/_header.tpl $@
	sed -i '' -e "s/SHORT_NAME/$*/g" $@

## Share

.PHONY: share
share: share/script.js share/style.css

share/script.js: $(JSFILES)
	closure-compiler --create_source_map share/script.js.map --js_output_file share/script.js $(JSFILES)
	echo "\n//# sourceMappingURL=script.js.map" >> share/script.js

share/red_style.css: src/scss/*.scss
	sass src/scss/red_style.scss:share/red_style.css

share/style.css: $(CSSFILES)
	cat $(CSSFILES) | cssmin > share/style.css

.PHONY: clean-share
clean-share:
	rm -f share/script.js share/script.js.map share/style.css
