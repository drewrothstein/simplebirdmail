$(document).ready(function() {
  var engine, remoteHost, template, empty;

  $.support.cors = true;

  remoteHost = 'https://<SOME_PROXY>';

  engine = new Bloodhound({
    identify: function(o) { return o.id_str; },
    queryTokenizer: Bloodhound.tokenizers.whitespace,
    datumTokenizer: Bloodhound.tokenizers.obj.whitespace('name', 'screen_name'),
    dupDetector: function(a, b) { return a.id_str === b.id_str; },
    remote: {
      url: remoteHost + '<SOME_PATH>%QUERY',
      wildcard: '%QUERY'
    }
  });

  function engineWithDefaults(q, sync, async) {
    if (q === '') {
      async([]);
    }

    else {
      engine.search(q, sync, async);
    }
  }

  $('#handle-input').typeahead({
    hint: $('.Typeahead-hint'),
    menu: $('.Typeahead-menu'),
    highlight: false,
    minLength: 2,
    classNames: {
      open: 'is-open',
      empty: 'is-empty',
      cursor: 'is-active',
      suggestion: 'Typeahead-suggestion',
      selectable: 'Typeahead-selectable'
    }
  }, {
    source: engineWithDefaults,
    displayKey: 'screen_name',
    templates: {
      suggestion: function(data) {
        return '<div class="ProfileCard u-cf">' +
               '<img class="ProfileCard-avatar" src="' + data.profile_image_url_https + '">' +
               '<div class="ProfileCard-details">' + 
                 '<div class="ProfileCard-realName">' + data.name + '</div>' + 
                  '<div class="ProfileCard-screenName">@' + data.screen_name + '</div>' +
                  '<div class="ProfileCard-description">' + data.description + '</div>' + 
                '</div>' + 
                '</div>'
      }
    }
  })
  .on('typeahead:asyncrequest', function() {
    $('.Typeahead-spinner').show();
  })
  .on('typeahead:asynccancel typeahead:asyncreceive', function() {
    $('.Typeahead-spinner').hide();
  });

  $('#handle-input').change(function() {
    $('#TWITTERHAN').val($('#handle-input').val());
    
    $('#mc_embed_signup form').attr("action",
      $('#mc_embed_signup form').attr("action").replace(/TWITTERHAN=.*/i, 'TWITTERHAN='+$('#handle-input').val()));
  });

  $('#mc-embedded-subscribe').click(function() {
    waitingDialog.show('Submitting request...');
    $('#handle-input').val('');
    $('#presubmit').hide('slow');
    setTimeout(function () {
      waitingDialog.hide();
      $('#success').show();
    }, 1500);
  });

});
