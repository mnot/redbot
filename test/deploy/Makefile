
source = ../../

deploy: clean
	cd $(source)/share; make clean; make
	cp -p $(source)/bin/webui.py .
	chmod a+x webui.py
	cp $(source)/bin/redbot redbot.py
	chmod a+x redbot.py
	cp -Rp $(source)/share/* static/
	cp -Rp $(source)/redbot .
	git clone --depth 1 git://github.com/mnot/thor.git thor-src
	ln -s thor-src/thor
	sed -i .old '/DEBUG_CONTROL/s/False/True/g' webui.py

clean:
	rm -f webui.py*
	rm -f redbot.py
	rm -rf thor-src
	rm -rf thor
	rm -rf redbot/*
	rm -rf exceptions/*
