
source = ../../

deploy: clean
	cd $(source)/share; make clean; make
	cp -p $(source)/bin/webui.py .
	chmod a+x webui.py
	cp $(source)/bin/redbot redbot.py
	chmod a+x redbot.py
	cp -Rp $(source)/share/* static/
	cp -Rp $(source)/redbot .
	sed -i .old '/DEBUG_CONTROL/s/False/True/g' webui.py

clean:
	rm -f webui.py*
	rm -f redbot.py
	rm -rf thor/*
	rm -rf redbot/*
	rm -rf exceptions/*
