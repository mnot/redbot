
/* Configuration */



function get_config () {
  
  "use strict";
  
  var scripts = document.getElementsByTagName('script');
  var myScript = scripts[ scripts.length - 1 ];
  var frag = unescape(myScript.src.replace(/^[^\#]+\#?/,''));
  return jQuery.parseJSON(frag);
}
var config = get_config();


$(document).ready(function() {
  
  "use strict";
  
  /* URI */
  
  var check_phrase = "Enter a http:// URI to check";
  if (config.redbot_uri) {
    $("#uri").val(config.redbot_uri);
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

  $("input").keypress(function (e) {
    if (e.which == 13) {
      $("#request_form").submit();
      return false;
    }
  });

  /* help */
  
  $("#help").toggle(function () {
    $(".help").fadeIn();
  }, function() {
    $(".help").fadeOut();
  });

  $(".help").click(function () {
    $(this).fadeOut();
  });

  /* single response display */

  var hidden_list = $("#hidden_list");

  $("span.hdr").hoverPopup(
    function(e){
      var name = $(this).attr('data-name');
      return $("li#header-" + name, hidden_list).html();
    },
    function(e){
      var name = $(this).attr('data-name');
      var offset = $(this).attr('data-offset');
      $("span.hdr[data-name='" + name + "']")
       .css({"font-weight": "bold", "color": "white"});
      $("li.msg").each(function(index, msg) {
        var msg_interesting = false;
        var subjects = $(msg).attr("data-subject").split(" ");
        for (var i=0; i < subjects.length; i++) {
          var subject = subjects[i];
          if (subject == "header-" + name) {
            msg_interesting = true;
            break;
          }
          if (subject == "offset-" + offset) {
            msg_interesting = true;
            break;
          }        
        }
        if (! msg_interesting) {
          $(msg).fadeTo(100, 0.15);
        }
      })
    },
    function(e){
      var name = $(this).attr('data-name');
      $("span.hdr[data-name='" + name + "']")
       .css({"font-weight": "normal", "color": "#ddd"});
      $("li.msg").fadeTo(100, 1.0);
    }
  );

  function find_header_targets(subjects, cb) {
    var targets = [];
    for (var i=0; i < subjects.length; i++) {
      var subject = subjects[i];
      var target;
      if (subject.indexOf('offset-') === 0) {
        target = $("span.hdr[data-offset='" + subject.slice(7) + "']");
      }
      else if (subject.indexOf('header-') === 0) {
        target = $("span.hdr[data-name='" + subject.slice(7) + "']");
      }
      if (target) {
        cb(target);
        targets.push(target);
      }
    }  
  }

  $("li.msg span").hoverPopup(
    function(e){
      return $("li#" + $(this).parent().attr('data-name'), hidden_list)
             .html();
    },
    function(e){
      find_header_targets(
        $(this).parent().attr('data-subject').split(" "),
        function(target) {
          target.css({"font-weight": "bold", "color": "white"});        
        }
      );
    },
    function(e){
      find_header_targets(
        $(this).parent().attr('data-subject').split(" "),
        function(target) {
          target.css({"font-weight": "normal", "color": "#ddd"});
        }
      );
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
    if (tid !== false) {
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

});