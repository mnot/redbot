"""\
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
    <script id="config" type="application/json">%(config)s</script>
    <script src="%(static)s/script.js" type="text/javascript"></script>
    <link rel="apple-touch-icon-precomposed" sizes="144x144"
     href="%(static)s/logo/apple-touch-icon-144x144.png" />
    <link rel="apple-touch-icon-precomposed" sizes="152x152"
     href="%(static)s/logo/apple-touch-icon-152x152.png" />
    <link rel="icon" href="%(static)s/logo/favicon.ico"/>
    <link rel="icon" type="image/png" href="%(static)s/logo/favicon-32x32.png" sizes="32x32" />
    <link rel="icon" type="image/png" href="%(static)s/logo/favicon-16x16.png" sizes="16x16" />
    <meta name="application-name" content="REDbot"/>
    <meta name="msapplication-TileColor" content="#FFFFFF" />
    <meta name="msapplication-TileImage" content="%(static)s/logo/mstile-144x144.png" />
    <meta property="og:type" content="website">
    <meta property="og:title" content="REDbot">
    <meta property="og:description" content="Lint for your HTTP resources">
    <meta property="og:url" content="https://redbot.org/">
    <meta property="og:site_name" content="REDbot">
    <meta property="og:image" content="https://redbot.org/static/logo/redbot-sq.png">
    %(extra_js)s
</head>

<body class="%(extra_body_class)s">

<form method="POST" id="save_form"
 action="?id=%(test_id)s&save=True%(descend)s">
</form>

<div id="request">
    <h1><a href="?"><span class="hilight"><abbr title="Resource Expert
    Droid">RED</abbr></span>bot</a>%(extra_title)s</h1>

    <form method="GET" id="request_form">
        <span class="help right hidden">Type in a URI here and press 'return' to
        check it. You can also specify request headers by clicking 'add a
        request header.'</span>
        <input type="url" name="uri" value="%(html_uri)s"
         id="uri" autocomplete="off" autofocus
         placeholder="Enter a http:// or https:// URL to check" /><br />
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
<div id="red_status"></div>
"""
