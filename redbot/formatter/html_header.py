u"""\
<!DOCTYPE html>
<html>
<head>
	<title>REDbot: &lt;%(html_uri)s&gt;</title>
	<meta http-equiv="content-type" content="text/html; charset=utf-8" />
	<meta name="ROBOTS" content="INDEX, NOFOLLOW" />
    <link rel="stylesheet" type="text/css" href="%(static)s/style.css">
	<!--[if IE]> 
    <style type="text/css">
        #right_column {
        	width: 650px;
            float: left;
    </style>
    <![endif]-->
    <script src='%(static)s/script.js#%(config)s' type="text/javascript"></script>
    %(extra_js)s
</head>

<body class="%(extra_body_class)s">

<div id="popup"></div>
<form method="POST" id="save_form"
 action="?id=%(test_id)s&save=True%(descend)s">
</form>

<div id="request">
    <h1><a href="?"><span class="hilight"><abbr title="Resource Expert Droid">RED</abbr></span>bot</a>%(extra_title)s</h1>

    <form method="GET" id="request_form">
        <span class="help right">Type in a URI here and press 'return' to
        check it. You can also specify request headers by clicking 'add a
        request header.'</span>
        <input type="url" name="uri" value="%(html_uri)s" 
         id="uri" autocomplete="off" autofocus /><br />
        <div id="req_hdrs"></div>
        <script type="text/javascript">
            document.write(
                '<div class="add_req_hdr">' +
                '<a href="#" id="add_req_hdr">add a request header</a>' +
                '</div>'
            )
        </script>
    </form>
</div>
"""
