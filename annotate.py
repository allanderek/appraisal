import pygments
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

class CodeHtmlFormatter(HtmlFormatter):

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
  <script src="annotate.js"></script>
  <link rel="stylesheet" href="annotate.css">
  </head>
  <body>
"""

if __name__ == '__main__':
    with open('test.py', 'r') as source_file:
        source_code = source_file.read()
        lexer = PythonLexer()
        formatter = CodeHtmlFormatter(
            full=False, 
            linespans="code-line",
            linenos=False,
            )
        with open('output.html', 'w') as output_file:
            output = pygments.highlight(source_code, lexer, formatter, output_file)