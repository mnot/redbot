
/* URI */

var check_phrase = "Enter a http:// URI to check";
if (redbot_uri) {
  $("#uri").val(redbot_uri);
} else if (! $("#uri").val()) {
  $("#uri").val(check_phrase);
  $("#uri").css({'color': '#ccc'});
}

$("#uri").focus(function(){
  if ($(this).val() == check_phrase) {
    $(this).val("");
    $("#uri").css({'color': '#111'});
  }
});

/* catch enter to work around IE8 */
$("input").keypress(function (e) {
  if (e.which == 13) {
    $("#request_form").submit();
  }
});


/* single response display */

var hidden_list = $("#hidden_list");

$("span.hdr").hoverPopup(
  function(e){
    var name = $(this).attr('name');
    return $("li#" + name, hidden_list).html();
  },
  function(e){
    var name = $(this).attr('name');
    $("span." + name).css({"font-weight": "bold", "color": "white"});
    $("li.msg:not(." + name + ")").fadeTo(100, 0.15);
    $("li.msg." + name).fadeTo(50, 1.0);
  },
  function(e){
    var name = $(this).attr('name');
    $("span." + name).css({"font-weight": "normal", "color": "#ddd"});
    $("li.msg").fadeTo(100, 1.0);
  }
);

$("li.msg span").hoverPopup(
  function(e){
    return $("li#" + $(this).parent().attr('name'), hidden_list).html();
  },
  function(e){
    var classes = $(this).parent().attr("class").split(" ");
    for (var i=0; i < classes.length; i++) {
      var c = classes[i];
      $("span.hdr[name='" + c +"']")
        .css({"font-weight": "bold", "color": "white"});
    }
  },
  function(e){
    var classes = $(this).parent().attr("class").split(" ");
    for (var i=0; i < classes.length; i++) {
      var c = classes[i];
      $("span.hdr[name='" + c +"']")
        .css({"font-weight": "normal", "color": "#ddd"});
    }
  }
);

$("h3").click(function(){
  $(this).next().slideToggle("normal");
});

$("#body_view").toggle(function() {
  $("#details").fadeOut('fast', function() {
    $("#body").fadeIn('fast');
    prettyPrint();
    $("#body_view").text("show messages");
  });
  return false;
}, function() {
  $("#body").fadeOut('fast', function() {
    $("#details").fadeIn('fast');
    $("#body_view").text("show body");
  });
  return false;
});

$("#save").click(function() {
  $("#save_form").submit();
})


/* multiple result display */

$("tr.droid").hoverIntent(function() {
  var classes = this.className.split(" ");
  $("li.msg").fadeTo(100, 0.15);
  for (var i=0; i < classes.length; i++) {
    var c = classes[i];
    if (c != 'droid') {
      $("li.msg:eq(" + c +")").fadeTo(50, 1.0);
    }
  }
  if (tid != false) {
    clearTimeout(tid);
    tid = false;
  }
}, function(){
  tid = setTimeout(function() {
    $("li.msg").fadeTo(50, 1.0);
  }, 100);
});

$("span.prob_num").hoverPopup(function(e) {
  return $(this).children(".hidden").html();
});

$("a.preview").hoverPopup(function(e) {
  var link = (this.title != "") ? this.title : this.href;
  return "<img src='" + link + "'/><br />" + link;
});
