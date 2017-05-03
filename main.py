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

@appraisal.command()
def reset_database():
    database.purge()

import flask
import flask_jsglue
import flask_wtf
from wtforms import StringField
from wtforms.validators import InputRequired

application = flask.Flask(__name__)
application.config['WTF_CSRF_ENABLED'] = False  # TODO: Obviously this.
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
    def __init__(self, repo_owner, repo, filepath, source_code=None):
        self.repo_owner = repo_owner
        self.repo = repo
        self.filepath = filepath
        if source_code is None:
            with open(filepath, 'r') as source_file:
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
    repo_url = 'https://api.github.com/repos/{0}/{1}'.format(owner, repo)
    gh_resp = requests.get('{0}/contents/{1}'.format(repo_url, filepath))
    gh_json = gh_resp.json()
    source_contents = gh_json['content']
    source_code = base64.b64decode(source_contents)
    source = SourceCode(owner, repo, filepath, source_code=source_code)
    return flask.render_template('view-source.jinja', source=source)

@application.route("/get-annotations", methods=['POST'])
def get_annotations():
    form = SourceSpecifierForm(flask.request.form)
    if not form.validate():
        return bad_request_response(message='You must provide a filename.')

    annotations = database.search(form.get_query())
    return flask.jsonify(annotations)

class SourceSpecifierForm(flask_wtf.FlaskForm):
    repo_owner = StringField('Repository Owner', [InputRequired()])
    repo = StringField('Repository', [InputRequired()])
    filepath = StringField('Filepath', [InputRequired()])

    def get_query(self):
        Source = tinydb.Query()
        return (
            (Source.repo_owner == self.repo_owner.data) &
            (Source.repo == self.repo.data) &
            (Source.filepath == self.filepath.data)
            )

class AnnotationSpecifierForm(SourceSpecifierForm):
    line_number = StringField('Line number', [InputRequired()])

    def get_query(self):
        Annot = tinydb.Query()
        return (
            (Annot.repo_owner == self.repo_owner.data) &
            (Annot.repo == self.repo.data) &
            (Annot.filepath == self.filepath.data) &
            (Annot.line_number == self.line_number.data)
            )

class AnnotationForm(AnnotationSpecifierForm):
    content = StringField('Content', [InputRequired()])


@application.route("/save-annotation", methods=['POST'])
def save_annotation():
    form = AnnotationForm(flask.request.form)
    if not form.validate():
        return bad_request_response(message='You must provide appropriate data.')

    query = form.get_query()
    if database.contains(query):
        database.update({'content': form.content}, query)
    else:
        database.insert({
            'repo_owner': form.repo_owner.data,
            'repo': form.repo.data,
            'filepath': form.filepath.data,
            'line_number': form.line_number.data,
            'content': form.content.data
        })
    return success_response()

@application.route("/delete-annotation", methods=['POST'])
def delete_annotation():
    form = AnnotationSpecifierForm(flask.request.form)

    if not form.validate():
        return bad_request_response(message='You must provide appropriate data.')

    query = form.get_query()
    # TODO: If there is no such thing in the database what happens?
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
