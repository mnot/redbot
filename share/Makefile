JSFILES = jquery.js jquery.hoverIntent.js prettify.js red_script.js red_popup.js red_req_headers.js 
CSSFILES = red_style.css prettify.css
YUI_COMPRESSOR_JAR = ~/Applications/yuicompressor-2.4.7.jar
BOWER = bower_components

JSFILES = $(BOWER)/jquery/jquery.min.js $(BOWER)/jquery-hoverIntent/jquery.hoverIntent.js $(BOWER)/google-code-prettify/bin/prettify.min.js red_script.js red_popup.js red_req_headers.js 
CSSFILES = red_style.css $(BOWER)/google-code-prettify/bin/prettify.min.css

.PHONY: all
all: script.js style.css jquery.min.map

.PHONY: clean
clean:
	rm script.js style.css red_style.css jquery.min.map

script.js:
	cat $(JSFILES) > script.js

style.css: red_style.css
	cat $(CSSFILES) | java -jar $(YUI_COMPRESSOR_JAR) --type css -o style.css

red_style.css: scss/*.scss
	sass scss/red_style.scss:red_style.css
	
jquery.min.map:
	cp $(BOWER)/jquery/jquery.min.map jquery.min.map