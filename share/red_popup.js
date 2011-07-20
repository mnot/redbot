/*
jQuery extension to hover a popup (#popup).
*/

var tid = false;
jQuery.fn.hoverPopup = function(fnText, fnOver, fnOut) {
  var fnOverPopup = function(e) {
    if (tid != false) {
      clearTimeout(tid);
      tid = false;
    }
    var text = fnText.call(this, e);
    if (text) {
      var pop_top = $(this).position().top + 15;
      var popup_width = 450;
      var popup_x;
      if (popup_width + 10 > window.innerWidth) {
        popup_x = 5;
        popup_width = window.innerWidth - 10;
      } else if (e.pageX + popup_width + 10 < window.innerWidth) {
        popup_x = e.pageX + 5;
      } else if (e.pageX - popup_width - 5 > 5) {
        popup_x = e.pageX - popup_width + 5;
      } else {
        popup_x = 5;
      }
      $("#popup")
        .fadeIn("fast")
        .css("top", pop_top + "px")
        .css("left", popup_x + "px")
        .css("width", popup_width + "px")
        .html(text);
      var margin = 28;
      var pop_height = $("#popup").height();
      var win_bottom = $(window).height() + $(window).scrollTop();
      if (win_bottom < pop_top + pop_height - margin) {
        var placement = win_bottom - margin - pop_height;
        $("#popup").animate({ top:placement }, 100);
      }
    } else {
      $("#popup").hide();
    }
    if (fnOver) {
      fnOver.call(this, e);
    }
  };
  var fnOutPopup = function(e) {
    tid = setTimeout(function(){
      $("#popup").fadeOut("fast");
    }, 350);
    if (fnOut) {
      fnOut.call(this, e);
    }
  };
  return jQuery.fn.hoverIntent.call(this, fnOverPopup, fnOutPopup);
};

$(document).ready(function() {
  $("#popup").hoverIntent(function(){
    if (tid != false) {
      clearTimeout(tid);
      tid = false;
    }
  }, function(){
    $("#popup").fadeOut("fast");
  });
  
});
