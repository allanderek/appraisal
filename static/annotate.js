/* global $ showdown hljs Flask source_information */

function delete_annotation(){
    var $annotation = $(this).closest('.annotation');
    var data = source_information;
    data.line_number = $annotation.attr('code-line');

    $.ajax({type: "POST",
      url: Flask.url_for('delete_annotation'),
      data: data,
      success: function(data){
          console.log('Successfully deleted the annotation');
          $annotation.remove();
      },
      error: function(data){
          console.log('something went wrong');
      }
    });
}

function save_annotation(){
    var textarea = this;
    var $annotation = $(textarea).closest('.annotation');
    var data = source_information;
    data.line_number = $annotation.attr('code-line');
    data.content = textarea.value;
    $.ajax({type: "POST",
      url: Flask.url_for('save_annotation'),
      data: data,
      success: function(data){
          console.log('Successfully saved the annotation');
      },
      error: function(data){
          console.log('something went wrong');
      }
    });
}

function process_annotation_output($annot_input, $annot_output){
    var converter = new showdown.Converter();
    var html = converter.makeHtml($annot_input.val());
    $annot_output.html(html);
    $annot_output.find('code').each(function(index){
        hljs.highlightBlock(this);
    }
    );
}


function add_annotation($code_line, content, focus_annot_textarea){
    var $annotation = $('\
        <div class="annotation">\
            <div class="annotation-toolbar">\
                <button class="toggle-annotation-editor">Toggle editor</button>\
                <button class="delete-annotation">delete</button>\
            </div>\
            <textarea class="annotation-input" />\
            <div class="annotation-output"></div>\
        </div>');
    $code_line.before($annotation);
    $annotation.attr('code-line', $code_line.attr('id'));
    $annotation.find('.delete-annotation').click(delete_annotation);
    var $annot_input = $annotation.find('.annotation-input');
    $annot_input.val(content);
    if (focus_annot_textarea){
        $annot_input.focus();
    }
    var $annot_output = $annotation.find('.annotation-output');

    // Set up the keyup event to format the common-mark into HTML
    $annot_input.keyup(function(){
        process_annotation_output($annot_input, $annot_output);
    });
    // Trigger that event immediately, we could skip this if 'content' is
    // blank (in particular for a 'new_annotation').
    $annot_input.trigger('keyup');
    $annot_input.keydown(function(event){
        event.stopPropagation();
        var keyCode = event.keyCode || event.which;
        var tab_key_code = 9;
        var escape_focus_key_code = 77;

        if (keyCode == tab_key_code) {
            event.preventDefault();

            var textarea = this;
            var start = textarea.selectionStart;
            var end = textarea.selectionEnd;
            var replacement = "    ";

            // set textarea value to: text before caret + tab + text after caret

            textarea.value =
                textarea.value.substring(0, start)
                + replacement
                + textarea.value.substring(end)
                ;

            // put caret at right position again
            textarea.selectionEnd = start + replacement.length;
            if (start === end){
                // So basically if there was no selection to begin with then
                // there shouldn't be now.
                textarea.selectionStart = textarea.selectionEnd;
            } else {
                // Not strictly necessary as it should be this already.
                textarea.selectionStart = start;
            }
            /* In theory we could also check for keys such as left/right arrow,
               backspace and delete etc. and do the right thing if we happen to
               be at 4 spaces. So for example backspace would delete 4 spaces if
               there are 4 spaces to the left of the caret (and no selection).
               However, I think once we start getting more to that level then we
               should consider using something like code-mirror.
             */
        } else if (keyCode == escape_focus_key_code && event.ctrlKey){
            event.preventDefault();
            $annot_input.blur();
        }
        });

    $annot_input.blur(save_annotation);

    $annotation.find('.toggle-annotation-editor').click(function(){
        $annot_input.toggle();
    });
}

function get_annotations(){
    $.ajax({type: "POST",
      url: Flask.url_for('get_annotations'),
      data: source_information,
      success: function(data){
          $.each(data['annotations'], function(index, annotation){
            var $code_line = $('#' + annotation['line_number']);
            add_annotation($code_line, annotation['content'], false);
          });
      },
      error: function(data){
          console.log('something went wrong');
      }
    });
}

function add_new_annotation(){
    add_annotation($(this), "", true);
}

function activate_line(line){
    var line_number = "#code-line-" + line;
    $('.code-line-container').removeClass('active-line');
    $('.code-line-container' + line_number).addClass('active-line');
}


function document_key_press(event){
    var $active_line = $(".active-line");
    var key_code_a = 65;
    var key_code_h = 72;
    var key_code_j = 74;
    var key_code_k = 75;

    function scroll_to_element($target){
        $('html, body').scrollTop($target.offset().top - 40);
    }

    function swap_active_line($current, $target){
        if($target.length){
            $target.addClass('active-line');
            $current.removeClass('active-line');
        }
    }

    function move_active_line(direction){
        var container_css = '.code-line-container';
        var $new_active_line = null;
        if (direction === 'up'){
            $new_active_line = $active_line.prevAll(container_css).first();
        } else if (direction === 'down'){
            $new_active_line = $active_line.nextAll(container_css).first();
        }
        if ($new_active_line.length){
            swap_active_line($active_line, $new_active_line);
            scroll_to_element($new_active_line);
        }
    }

    if (event.which === key_code_j){
        move_active_line('down');
    } else if (event.which === key_code_k){
        move_active_line('up');
    } else if (event.which === key_code_a){
        add_annotation($active_line, '', true);
        return false;
    } else if (event.which === key_code_h){
        var $next_annotation = $active_line.nextAll('.annotation').first();
        if ($next_annotation.length){
            $next_annotation.find('.annotation-input').focus();
            $new_active_line = $next_annotation.nextAll('.code-line-container').first();
            swap_active_line($active_line, $new_active_line);
        }
        return false;
    }
    return true;
}

$(document).ready(function(){
    $('.code-line-container').click(add_new_annotation);
    get_annotations();
    activate_line(0); // Assumes there is at least one line.
    $(document).keydown(document_key_press);
});