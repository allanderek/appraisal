import os.path
import base64

import pygments
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

import requests


class CodeHtmlFormatter(HtmlFormatter):
    def __init__(self, *args, output_filename=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_filename = output_filename

    def wrap(self, source, outfile):
        return self._wrap_pre_code(source)

    def _wrap_pre_code(self, source):
        for line_number, (is_code, source_line) in enumerate(source):
            if is_code == 1:
                source_line = """<pre id="code-line-{0}" class="code-line-container"
                   ><code class="code-line">{1}</code></pre>""".format(line_number, source_line)
            yield is_code, source_line


import click
import jinja2

@click.group()
def appraisal():
    pass


@appraisal.command()
@click.argument('input_filename')
@click.argument('output_filename')
def highlight(input_filename, output_filename):
    with open(input_filename, 'r') as source_file:
        source_code = source_file.read()
    source = SourceCode(input_filename, source_code=source_code)
    env = jinja2.Environment(
        loader=jinja2.PackageLoader('main', 'templates/'),
        autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
    template = env.get_template('view-source.jinja')
    with open(output_filename, 'w') as outfile:
        outfile.write(template.render(source=source))

import tinydb

database_filename = 'generated/play.json'
database = tinydb.TinyDB(database_filename)

def has_extension(filename, extension):
    ext = os.path.splitext(filename)[-1].lower()
    return ext == extension

def add_file_to_database(filename):
    database.insert({'filename': filename,
                     'line-number': 'code-line-3',
                     'content': "# Mighty mouse is here."
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


def error_response(response_code, message):
    """Used for producing an ajax response that indicates failure."""
    response = flask.jsonify({'message': message})
    response.status_code = response_code
    return response

def unauthorized_response(message=None):
    message = message or 'You must be logged-in to do that.'
    return error_response(401, message)

def bad_request_response(message=None):
    message = message or 'The client made a bad request.'
    return error_response(400, message)

def success_response(results=None):
    results = results or {}
    results['success'] = True
    return flask.jsonify(results)

class SourceCode(object):
    def __init__(self, filename, source_code=None):
        self.filename = filename
        if source_code is None:
            with open('tests/{}'.format(filename), 'r') as source_file:
                source_code = source_file.read()
        lexer = PythonLexer()
        formatter = CodeHtmlFormatter(
            full=False,
            linenos=False,
            )
        self.highlighted_source = pygments.highlight(source_code, lexer, formatter)

@application.route("/", methods=['GET'])
def homepage():
    repository_url = 'https://api.github.com/repos/kennethreitz/requests'
    gh_resp = requests.get('{0}/git/trees/master'.format(repository_url))
    master = gh_resp.json()
    gh_resp = requests.get(
        '{0}/git/trees/{1}'.format(repository_url, master['sha']),
        params={'recursive': 1})
    tree = gh_resp.json()
    return flask.render_template('welcome.jinja', tree=tree)


@application.route("/view-source/<owner>/<repo>/<path:filepath>", methods=['GET'])
def view_source(owner, repo, filepath):
    filename = os.path.basename(filepath)
    repo_url = 'https://api.github.com/repos/kennethreitz/requests'
    gh_resp = requests.get('{0}/contents/{1}'.format(repo_url, filepath))
    gh_json = gh_resp.json()
    source_contents = gh_json['content']
    source_code = base64.b64decode(source_contents)
    source = SourceCode(filename, source_code=source_code)
    return flask.render_template('view-source.jinja', source=source)

@application.route("/get-annotations", methods=['POST'])
def get_annotations():
    filename = flask.request.form.get('filename', None)
    if not filename:
        return bad_request_response(message='You must provide a filename.')

    query = tinydb.Query()
    annotations = database.search(query.filename == filename)
    return flask.jsonify(annotations)


@application.route("/save-annotation", methods=['POST'])
def save_annotation():
    filename = flask.request.form.get('filename', None)
    line_number = flask.request.form.get('line-number', None)
    content = flask.request.form.get('content', None)

    if None in [filename, line_number, content]:
        return bad_request_response(message='You must provide appropriate data.')

    query = tinydb.Query()
    query = (query.filename == filename) & (query['line-number'] == line_number)
    if database.contains(query):
        database.update({'content': content}, query)
    else:
        database.insert({
            'filename': filename,
            'line-number': line_number,
            'content': content
        })
    return success_response()

@application.route("/delete-annotation", methods=['POST'])
def delete_annotation():
    # TODO: In general we need to implement CSRF
    # Here we are assuming you are deleting the annotation, but we are not
    # checking that the content is the same, that is, that we have not updated
    # the content from elsewhere.
    filename = flask.request.form.get('filename', None)
    line_number = flask.request.form.get('line-number', None)

    if None in [filename, line_number]:
        return bad_request_response(message='You must provide appropriate data.')

    query = tinydb.Query()
    query = (query.filename == filename) & (query['line-number'] == line_number)
    database.remove(query)
    return success_response()

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
