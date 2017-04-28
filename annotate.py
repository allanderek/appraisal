import os.path

import pygments
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

class CodeHtmlFormatter(HtmlFormatter):
    def __init__(self, *args, output_filename=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_filename = output_filename

    def wrap(self, source, outfile):
        return self._wrap_pre_code(source)

    def _wrap_pre_code(self, source):
        for is_code, source_line in source:
            if is_code == 1:
                source_line = '<pre class="code-line-pre"><code class="code-line">{}</code></pre>'.format(source_line)
            yield is_code, source_line


import click

@click.group()
def appraisal():
    pass


@appraisal.command()
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

import flask
import flask_jsglue

application = flask.Flask(__name__)
jsglue = flask_jsglue.JSGlue(application)

@application.route("/view-source/", methods=['GET'])
def view_source():
    with open('tests/example.py', 'r') as source_file:
        source_code = source_file.read()
    lexer = PythonLexer()
    formatter = CodeHtmlFormatter(
        full=False,
        linespans="code-line",
        linenos=False,
        )
    source = pygments.highlight(source_code, lexer, formatter)
    return flask.render_template('view-source.jinja', source=source)

@application.route("/get-annotations", methods=['POST'])
def get_annotations():
    annotations = [
        { 'line-number': '7',
          'content': "# Here I am to save the day." }
        ]
    return flask.jsonify(annotations)

@appraisal.command()
def runserver():
    extra_dirs = ['static/', 'templates/']
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, dirs, files in os.walk(extra_dir):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    extra_files.append(filename)
    application.run(
        port=8080,
        host='0.0.0.0',
        debug=True,
        extra_files=extra_files
        )

if __name__ == '__main__':
    appraisal()
