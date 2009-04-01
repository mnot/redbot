"""\
<html>
<head>
	<title>RED: &lt;%(uri)s&gt;</title>
	<link rel="stylesheet" type='text/css' href="red_style.css">
</head>
<script src="jquery.js"></script>
<script>
var tid = false;
$(document).ready(function(){
	$("span").hover(
	function(){
		var classes = this.className.split(" ");
		for (var i=0; i < classes.length; i++) {
			var c = classes[i];
			if (true) { 
			 var marker_class = c;
			}
		};
		$("span." + marker_class).css({"font-weight": "bold", "color": "white"});
		$("li:not(." + marker_class + ")").fadeTo(100, 0.15);
		$("li." + marker_class).fadeTo(60, 1.0);
		if (tid != false) {
			clearTimeout(tid);
			tid = false;
		};
	}, function(){
		var classes = this.className.split(" ");
		for (var i=0; i < classes.length; i++) {
			var c = classes[i];
			if (true) { 
			 var marker_class = c;
			}
		};
		$("span." + marker_class).css({"font-weight": "normal", "color": "#ddd"});
		tid = setTimeout(function(){
			$("li").fadeTo(100, 1.0);
		}, 100);
	});

	$("li").mouseover(function(){
		classes = this.className.split(" ");
		for (var i=0; i < classes.length; i++) {
			var c = classes[i];
			$("span." + c ).css({"font-weight": "bold", "color": "white"});
		};
	});

	$("li").mouseout(function(){
		classes = this.className.split(" ");
		for (var i=0; i < classes.length; i++) {
			var c = classes[i];
			$("span." + c ).css({"font-weight": "normal", "color": "#ddd"});
		};
	});
	
	$("li").hover(function(){
		var content = this.getElementsByTagName("span")[0].innerHTML;
		var lm = document.getElementById("long_mesg");  
		var doc = lm.contentDocument;
		if (doc == undefined || doc == null)
		    doc = lm.contentWindow.document;
		doc.open();
		doc.write("<style type='text/css'>body {margin: 0; padding:0; background-color: #eee; color: #111; font: 1.05em/1.15em sans-serif; margin: 1em 4em;}</style>");
		doc.write(content);
		doc.close();
	});

	$("h3").click(function(){
		$(this).next().slideToggle("normal");
	});

	$("a.view").click(function(){
		document.all.long_mesg.src = this.getAttribute('title');
	});
});

</script>

<body>
<div id="main">

<h1><span class="hilight">r</span>esource <span class="hilight">e</span>xpert <span class="hilight">d</span>roid</h1>

<p><form method="GET"><input type="text" name="uri" value="%(uri)s"/></form></p>
"""