"""\
<html>
<head>
	<title>RED: &lt;%(html_uri)s&gt;</title>
	<link rel="stylesheet" type='text/css' href="red_style.css">
	<meta http-equiv="content-type" content="text/html; charset=utf-8" />
	<meta name="ROBOTS" content="INDEX, NOFOLLOW" />
<script src="jquery.js"></script>
<script src="./jquery.hoverIntent.js"></script>
<script>
var tid = false;
var tid2 = false;

$(document).ready(function(){
    $("span.hdr").hover(
    function(e){
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
        $(".mesg_sidebar").css({"position": "fixed"});
        var detail_msg = $("li.msg." + marker_class + ".detail > .hidden_desc").html();
        if (detail_msg) {
            if (tid2 != false) {
                clearTimeout(tid2);
                tid2 = false;
            }
            $("#popup")
                .fadeIn("fast")
                .css("top", (e.pageY - 15) + "px")
                .css("left", (e.pageX + 15) + "px")
                .html(detail_msg);
        }
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
        tid2 = setTimeout(function(){
            $("#popup").fadeOut("fast");
        }, 200);
    });

    $("#popup").hover(function(){
        if (tid2 != false) {
            clearTimeout(tid2);
            tid2 = false;
        }
    }, function(){
        $("#popup").fadeOut("fast");
    });

/* commented out because of issues with bullets disappearing
    $("span.hdr").click(
        function(){
            var classes = this.className.split(" ");
            for (var i=0; i < classes.length; i++) {
                var c = classes[i];
                if (c != 'hdr') {
                    var marker_class = c;
                }
            };
            $("li.msg." + marker_class).slideDown("fast");
            $("li.msg:not('." + marker_class + "')").slideUp("fast");
        }
    );

    $("span.hdr").dblclick(
        function(){
            $("li.msg").slideDown("fast");
        }
    );
*/

    $("tr.droid").hoverIntent(
    function(){
        var classes = this.className.split(" ");
        $("li.msg").fadeTo(100, 0.15);
        for (var i=0; i < classes.length; i++) {
            var c = classes[i];
            if (c != 'droid') {
                $("li.msg:eq(" + c +")").fadeTo(50, 1.0);
            }
        };
        if (tid != false) {
            clearTimeout(tid);
            tid = false;
        };
    }, function(){
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
        $(".mesg_sidebar").css({"position": "fixed"});
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
        $(".mesg_sidebar").css({"position": "absolute"});
        $("#long_mesg").html($("#link_list").html());
    });

    var check_phrase = "Enter a HTTP URI to check";
    var uri = "%(js_uri)s";
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

    $("span.prob_num").hoverIntent(function(e){
        $(this).children(".prob_title")
            .css("display", "block")
            .css("top", (e.pageY - 20) + "px")
            .css("left", (e.pageX - 168) + "px")
            .fadeIn("fast");
    }, function(){
        $(this).children(".prob_title").css("display", "none");
    });

    $("span.prob_num").mousemove(function(e){
        $(this).children(".prob_title")
            .css("top", (e.pageY - 20) + "px")
            .css("left", (e.pageX - 168) + "px");
    });

    $("a.preview").hoverIntent(function(e){
        this.old_t = this.title;
        this.title = "";
        var link = (this.old_t != "") ? this.old_t : this.href;
        $("body").append("<p id='preview'><img src='" + link + "'/><br />" + link + "</p>");
        $("#preview")
            .css("top", (e.pageY - 10) + "px")
            .css("left", (e.pageX + 25) + "px")
            .fadeIn("fast");
    }, function(){
        $("#preview").remove();
        this.title = this.old_t;
    });

    $("a.preview").mousemove(function(e){
        $("#preview")
            .css("top", (e.pageY - 10) + "px")
            .css("left", (e.pageX + 25) + "px");
    });

});

</script>
</head>

<body>

<div id="popup">foo</div>

<div id="header">
<h1><span class="hilight">R</span>esource <span class="hilight">E</span>xpert <span class="hilight">D</span>roid</h1>

<form method="GET">
<input type="text" name="uri" value="%(html_uri)s" id="uri"/><br />
</form>
</div>
"""