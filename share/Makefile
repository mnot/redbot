BOWER = bower_components
JSFILES = $(BOWER)/jquery/dist/jquery.js $(BOWER)/jquery-hoverIntent/jquery.hoverIntent.js $(BOWER)/google-code-prettify/src/prettify.js red_script.js red_popup.js red_req_headers.js 
CSSFILES = red_style.css $(BOWER)/google-code-prettify/src/prettify.css

.PHONY: all
all: script.js style.css

.PHONY: clean
clean:
	rm -f script.js style.css red_style.css script.js.map

script.js: $(JSFILES)
	closure-compiler --create_source_map script.js.map --js_output_file script.js $(JSFILES) 
	echo "\n//# sourceMappingURL=script.js.map" >> script.js

style.css: red_style.css
	cat $(CSSFILES) | cssmin > style.css

red_style.css: scss/*.scss
	sass scss/red_style.scss:red_style.css
