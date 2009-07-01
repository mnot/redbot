"""\
<html>
<head>
	<title>RED: &lt;%(html_uri)s&gt;</title>
	<link rel="stylesheet" type='text/css' href="red_style.css">
	<meta http-equiv="content-type" content="text/html; charset=utf-8" />
	<meta name="ROBOTS" content="INDEX, NOFOLLOW" />
</head>
<script src="jquery.js"></script>
<script src="./jquery.hoverIntent.js"></script>
<script>
var tid = false;
var frame_css = "<style type='text/css'>body {margin: 0; padding:0; background-color: #eee; color: #111; font: 1em/1.1em sans-serif;}</style>";

$(document).ready(function(){
	$("span.hdr").hover(
	function(){
		var classes = this.className.split(" ");
		for (var i=0; i < classes.length; i++) {
			var c = classes[i];
			if (c != 'hdr') { 
			 var marker_class = c;
			}
		};
		$("span." + marker_class).css({"font-weight": "bold", "color": "white"});
		$("li.msg:not(." + marker_class + ")").fadeTo(100, 0.15);
		$("li.msg." + marker_class).fadeTo(50, 1.0);
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
			$("li.msg").fadeTo(50, 1.0);
		}, 100);
	});
	
	$("li.msg").hoverIntent(function(){
		classes = this.className.split(" ");
		for (var i=0; i < classes.length; i++) {
			var c = classes[i];
			$("span." + c ).css({"font-weight": "bold", "color": "white"});
		};
		$("#long_mesg").css({"position": "fixed"});
		$("#long_mesg").html($("span:first", this).html());
	}, function(){
		classes = this.className.split(" ");
		for (var i=0; i < classes.length; i++) {
			var c = classes[i];
			$("span." + c ).css({"font-weight": "normal", "color": "#ddd"});
		};	
	});

	$("h3").click(function(){
		$(this).next().slideToggle("normal");
	});
	
	$("a.link_view").click(function(){
		$("#long_mesg").css({"position": "absolute"});
		$("#long_mesg").html($("#link_list").html());
	});

	var check_phrase = "Enter a HTTP URI to check";
	var uri = "%(uri)s";
	$(document).ready(function(){
		if (uri) {
			$("#uri").val(uri);		
		} else if (! $("#uri").val()) {
			$("#uri").val(check_phrase);
			$("#uri").css({'color': '#ccc'});
		}
	});

	$("#uri").focus(function(){
		if ($(this).val() == check_phrase) {
			$(this).val("");
			$("#uri").css({'color': '#111'});
		}
	});

});

</script>

<body>
<div id="main">

<h1><span class="hilight">R</span>esource <span class="hilight">E</span>xpert <span class="hilight">D</span>roid</h1>

<p><form method="GET"><input type="text" name="uri" value="%(html_uri)s" id="uri"/></form></p>
"""