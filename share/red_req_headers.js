
/* request headers */


var known_req_hdrs = {
  'Accept-Language': ['', 'en', 'en-us', 'en-uk', 'fr'],
  'Cache-Control': ['', 'no-cache', 'only-if-cached'],
  'Cookie': null,
  'Referer': null,
  'User-Agent': [ 
    "RED/" + redbot_version + " (http://redbot.org/about)",
    "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Win64; x64; Trident/4.0)",
    "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; )",
    "Mozilla/5.0 (X11; U; Linux x86_64; en-US) Gecko Firefox/3.0.8",
    "Opera/9.80 (Windows NT 5.1; U; cs) Presto/2.2.15 Version/10.00",
  ]
};

var red_req_hdrs = [
  'accept-encoding',
  'if-modified-since',
  'if-none-match',
  'connection',
  'transfer-encoding',
  'content-length'
];

$("#add_req_hdr").click(function(){
  add_req_hdr();
  return false;
});


function add_req_hdr(hdr_name, hdr_val){
  var hdr_shell = "<div class='req_hdr'>";
  hdr_shell += "<a href='#' class='delete_req_hdr'>x</a> ";
  hdr_shell += "<span class='hdr_name'></span>";
  hdr_shell += ": <span class='hdr_val'></span>";
  hdr_shell += "<input type='hidden' name='req_hdr' value=''/>";
  hdr_shell += "</div>";
  $("#req_hdrs").append(hdr_shell);
  var req_hdr = $("#req_hdrs > .req_hdr:last");
  if (hdr_name == null || hdr_name in known_req_hdrs) {
    var name_html = "<select class='hdr_name'><option/>";
    for (name in known_req_hdrs) {
      if (name == hdr_name) {
        name_html += "<option selected='true'>" + name + "</option>";
      } else {
        name_html += "<option>" + name + "</option>";
      }
    }
    name_html += "<option value='other...'>other...</option>";
    name_html += "</select>";
    $(".hdr_name", req_hdr).replaceWith(name_html);

    if (hdr_name != null) {
      known_hdr_vals = known_req_hdrs[hdr_name];
      if (known_hdr_vals == null) {
        $(".hdr_val", req_hdr)
         .replaceWith('<input class="hdr_val" type="text"/>');
        $(".hdr_val", req_hdr).val(hdr_val);
      } else if (jQuery.inArray(hdr_val, known_hdr_vals) > -1) {
        var val_html = "<select class='hdr_val'>";
        val_html += "<option />";
        for (i in known_hdr_vals) {
          var val = known_hdr_vals[i];
          if (hdr_val == val) {
            val_html += "<option selected='true'>" + val + "</option>";
          } else {
            val_html += "<option>" + val + "</option>";
          }
        }
        val_html += "<option value='other...'>other...</option>";
        val_html += "</select>";
        $(".hdr_val", req_hdr).replaceWith(val_html);
      } else if (hdr_val != null) {
        $(".hdr_val", req_hdr)
         .replaceWith('<input class="hdr_val" type="text"/>');
        $(".hdr_val", req_hdr).val(hdr_val);
      }
      $("input[type=hidden]", req_hdr).val(hdr_name + ":" + hdr_val);
    }
  } else {
    $(".hdr_name", req_hdr)
     .replaceWith('<input class="hdr_name" type="text"/>');
    $(".hdr_name", req_hdr).val(hdr_name);
    $(".hdr_val", req_hdr)
     .replaceWith('<input class="hdr_val" type="text"/>');
    $(".hdr_val", req_hdr).val(hdr_val);
    $("input[type=hidden]", req_hdr).val(hdr_name + ":" + hdr_val);
  }

  /* populate the value when the header name is changed */
  $("select.hdr_name:last").bind("change", function(){
    var req_hdr = $(this).closest(".req_hdr");
    var hdr_name = $(".hdr_name > option:selected", req_hdr).val()
    var hdr_val = "";
    if (hdr_name in known_req_hdrs) {
      if (known_req_hdrs[hdr_name] == null) {
        hdr_val = "<input class='hdr_val' type='text'/>";
        $(".hdr_val", req_hdr).replaceWith(hdr_val);
        bind_text_changes(req_hdr);
      } else {
        hdr_val = "<select class='hdr_val'>";
        for (val in known_req_hdrs[hdr_name]) {
          hdr_val += "<option>" + known_req_hdrs[hdr_name][val] + "</option>";
        }
        hdr_val += "<option value='other...'>other...</option>";
        hdr_val += "</select>";
        $(".hdr_val", req_hdr).replaceWith(hdr_val);
        $("select.hdr_val", req_hdr).bind("change", function(){
          var hdr_val = "";
          if ($(".hdr_val > option:selected", req_hdr).val() == "other...") {
            $(".hdr_val", req_hdr)
             .replaceWith("<input class='hdr_val' type='text'/>");
            bind_text_changes(req_hdr);
          } else {
            hdr_val = $(".hdr_val > option:selected", req_hdr).val();
          }
          $("input[type=hidden]", req_hdr).val(hdr_name + ":" + hdr_val);
        });
      }
    } else if (hdr_name == "other...") {
      $(".hdr_name", req_hdr)
       .replaceWith("<input class='hdr_name' type='text'/>");
      $(".hdr_val", req_hdr)
       .replaceWith("<input class='hdr_val' type='text'/>");
      bind_text_changes(req_hdr);

      /* alert on dangerous changes */
      $("input.hdr_name", req_hdr).bind("change", function() {
        var hdr_name = $(".hdr_name:text", req_hdr).val();
        if (jQuery.inArray(hdr_name.toLowerCase(), red_req_hdrs) > -1) {
          alert("The " + hdr_name + " request header is used by RED in its \
tests. Setting it yourself can lead to unpredictable results; please remove it.");
        }
      });
    }
  });

  /* handle the delete button */
  $(".delete_req_hdr:last").bind("click", function(){
    var req_hdr = $(this).closest(".req_hdr");
    req_hdr.remove();
    return false;
  });
}

function bind_text_changes(req_hdr) {
  /* handle textbox changes */
  $("input.hdr_name, input.hdr_val", req_hdr).bind("change", function() {
    var hdr_name = $(".hdr_name", req_hdr).val();
    var hdr_val = $(".hdr_val:text", req_hdr).val();
    $("input[type=hidden]", req_hdr).val(hdr_name + ":" + hdr_val);
  });
}

function init_req_hdrs() {
  for (i in redbot_req_hdrs) {
    var req_hdr = redbot_req_hdrs[i];
    add_req_hdr(req_hdr[0], req_hdr[1]);
  }
  return false;
}

init_req_hdrs();