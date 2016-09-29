
source = ../../
PYTHON=python

all: redbot

.PHONY: server
server: clean all
	$(PYTHON) webui.py 8080 static/

redbot-share:
	cd $(source)/share; make

redbot: clean-redbot
	cp -p $(source)/bin/webui.py .
	chmod a+x webui.py
	cp $(source)/bin/redbot redbot.py
	chmod a+x redbot.py
	mkdir -p static
	cp -Rp $(source)/share/* static/
	cp -Rp $(source)/redbot .
	sed -i=.old '/DEBUG_CONTROL/s/False/True/g' webui.py

share: clean-share
	cd $(source)/share; make

thor: clean-thor
	git clone --depth 1 git://github.com/mnot/thor.git thor-src
	ln -s thor-src/thor

clean: clean-redbot clean-thor

clean-redbot:
	rm -f webui.py*
	rm -f redbot.py
	rm -rf redbot/*
	rm -rf exceptions/*

clean-thor:
	rm -rf thor-src
	rm -rf thor
