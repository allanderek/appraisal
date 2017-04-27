import os.path

import pygments
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

class CodeHtmlFormatter(HtmlFormatter):
    def __init__(self, *args, output_filename=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_filename = output_filename

    def wrap(self, source, outfile):
        return self._wrap_html(source)

    def _wrap_html(self, source):
        yield 0, self.html_head
        for is_code, source_line in source:
            if is_code == 1:
                source_line = '<pre class="code-line-pre"><code class="code-line">{}</code></pre>'.format(source_line)
            yield is_code, source_line
        yield 0, self.html_foot
    
    
    html_foot = "</body></html>"
    @property
    def html_head(self):
        # Basically assuming that the .css and .js files that we need to include
        # are in the same place as this script that we're running. Not really
        # entirely clear that this is the correct thing to do.
        output_dir = os.path.dirname(self.output_filename)
        path_to_here = os.path.relpath(__file__, start=output_dir)
        include_dir = os.path.dirname(path_to_here)
        annotate_js = os.path.join(include_dir, 'annotate.js')
        annotate_css = os.path.join(include_dir, 'annotate.css')
        html_head = """
<!DOCTYPE>
<html>
<head>
  <title></title>
  <meta http-equiv="content-type" content="text/html; charset=utf-8">
  <script
    src="https://code.jquery.com/jquery-3.2.1.min.js"
    integrity="sha256-hwg4gsxgFZhOsEEamdOYGBf13FyQuiTwlAQgxVSNgt4="
    crossorigin="anonymous"></script>
  <script src="https://cdn.rawgit.com/showdownjs/showdown/1.6.3/dist/showdown.min.js"></script>
  
  <link rel="stylesheet" href="//cdnjs.cloudflare.com/ajax/libs/highlight.js/9.11.0/styles/default.min.css">
  <script src="//cdnjs.cloudflare.com/ajax/libs/highlight.js/9.11.0/highlight.min.js"></script>
  <script src="{0}"></script>
  <link rel="stylesheet" href="{1}">
  </head>
  <body>
""".format(annotate_js, annotate_css)
        return html_head

import click

@click.command()
@click.argument('input_filename')
@click.argument('output_filename')
def highlight(input_filename, output_filename):
    with open(input_filename, 'r') as source_file:
        source_code = source_file.read()
        lexer = PythonLexer()
        formatter = CodeHtmlFormatter(
            full=False, 
            linespans="code-line",
            linenos=False,
            output_filename=output_filename
            )
        with open(output_filename, 'w') as output_file:
            output = pygments.highlight(source_code, lexer, formatter, output_file)

if __name__ == '__main__':
    highlight()
