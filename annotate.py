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

import tinydb

database_filename = 'generated/play.json'
database = tinydb.TinyDB(database_filename)

def has_extension(filename, extension):
    ext = os.path.splitext(filename)[-1].lower()
    return ext == extension

def add_file_to_database(filename):
    database.insert({'filename': filename,
                     'annotations': [{ 'line-number': '3',
                     'content': "# Mighty mouse is here."}]
                    })

@appraisal.command()
def reset_database():
    database.purge()

    file_directories = ['tests/']
    for file_directory in file_directories:
        for dirname, _dirs, files in os.walk(file_directory):
            for filename in files:
                filepath = os.path.join(dirname, filename)
                if os.path.isfile(filepath) and has_extension(filename, '.py'):
                    add_file_to_database(filename)


import flask
import flask_jsglue

application = flask.Flask(__name__)
jsglue = flask_jsglue.JSGlue(application)


class SourceCode(object):
    def __init__(self, filename):
        self.filename = filename
        with open('tests/{}'.format(filename), 'r') as source_file:
            source_code = source_file.read()
        lexer = PythonLexer()
        formatter = CodeHtmlFormatter(
            full=False,
            linespans="code-line",
            linenos=False,
            )
        self.highlighted_source = pygments.highlight(source_code, lexer, formatter)

@application.route("/view-source/<filename>", methods=['GET'])
def view_source(filename):
    source = SourceCode(filename)
    return flask.render_template('view-source.jinja', source=source)

@application.route("/get-annotations", methods=['POST'])
def get_annotations():
    filename = flask.request.form.get('filename', None)
    if not filename:
        annotations = []
    else:
        query = tinydb.Query()
        files = database.search(query.filename == filename)
        if not files:
            annotations = []
        else:
            file = files[0]
            annotations = file['annotations']
    return flask.jsonify(annotations)

@appraisal.command()
def runserver():
    extra_dirs = ['static/', 'templates/']
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, _dirs, files in os.walk(extra_dir):
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
