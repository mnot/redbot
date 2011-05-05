JSFILES = jquery.js jquery.hoverIntent.js jquery.base64.js prettify.js
CSSFILES = red_style.css prettify.css
YUI_COMPRESSOR_JAR = ~/Applications/yuicompressor-2.4.3.jar

all: script.js style.css

clean:
	rm script.js style.css

script.js:
	cat $(JSFILES) > script.js
	
style.css:
	cat $(CSSFILES) | java -jar $(YUI_COMPRESSOR_JAR) --type css -o style.css
