JSFILES = jquery.js jquery.hoverIntent.js prettify.js red_script.js red_popup.js red_req_headers.js 
CSSFILES = red_style.css prettify.css
YUI_COMPRESSOR_JAR = ~/Applications/yuicompressor-2.4.7.jar

.PHONY: all
all: script.js style.css

.PHONY: clean
clean:
	rm script.js style.css red_style.css

script.js:
	cat $(JSFILES) > script.js

style.css: red_style.css
	cat $(CSSFILES) | java -jar $(YUI_COMPRESSOR_JAR) --type css -o style.css

red_style.css:
	sass scss/red_style.scss:red_style.css