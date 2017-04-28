/* global $ showdown hljs Flask */
function add_annotation(){
    var $annotation = $(`
        <div class="annotation">
            <div class="annotation-toolbar">
                <button class="toggle-annotation-editor">Toggle editor</button>
                <button class="delete-annotation">delete</button>
            </div>
            <textarea class="annotation-input" />
            <div class="annotation-output"></div>
        </div>`);
    $(this).before($annotation);
    $annotation.find('.delete-annotation').click(delete_annotation);
    var $annot_input = $annotation.find('.annotation-input');
    var $annot_output = $annotation.find('.annotation-output');
    $annot_input.keyup(function(){
        var converter = new showdown.Converter();
        var html = converter.makeHtml($annot_input.val());
        $annot_output.html(html);
        $annot_output.find('code').each(function(index){
            hljs.highlightBlock(this);
        }
        );
    });
    $annot_input.keydown(function(event){
        var keyCode = event.keyCode || event.which;

        if (keyCode == 9) {
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
        }
        });

    $annotation.find('.toggle-annotation-editor').click(function(){
        $annot_input.toggle();
    });
}

function delete_annotation(){
    $(this).closest('.annotation').remove();
}

function get_annotations(){
    $.ajax({type: "POST",
      url: Flask.url_for('get_annotations'),
      data: { 'document': 'whatever' },
      success: function(data){
          console.log(data);
          $('body').append(data);
      },
      error: function(data){
          console.log('something went wrong');
      }
    });
}

$(document).ready(function(){
    $('.code-line-pre').click(add_annotation);
    get_annotations();
});