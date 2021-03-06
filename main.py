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

def generated_file_path(additional_path):
    basedir = os.path.abspath(os.path.dirname(__file__))
    generated_dir = os.path.join(basedir, 'generated/')
    return os.path.join(generated_dir, additional_path)

from pony import orm

database = orm.Database()
def set_database(db_file='play.sqlite', reset=False):
    database_filename = generated_file_path(db_file)
    # Note that for testing this could maybe be :memory: but then again
    # sometimes it is nice to look at the database after testing has finished.
    # We may have to actually delete the file if reset is true.
    database.bind('sqlite', database_filename, create_db=True)
    database.generate_mapping(create_tables=True)
    if reset:
        database.drop_all_tables(with_all_data=True)
        database.create_tables()

class Annotation(database.Entity):
    repo = orm.Required(str)
    repo_owner = orm.Required(str)
    filepath = orm.Required(str)
    line_number = orm.Required(str)
    content = orm.Required(str)

    def jsonify(self):
        return { 'repo': self.repo,
                 'repo_owner': self.repo_owner,
                 'filepath': self.filepath,
                 'line_number': self.line_number,
                 'content': self.content }


def has_extension(filename, extension):
    ext = os.path.splitext(filename)[-1].lower()
    return ext == extension

@appraisal.command()
def reset_database():
    set_database(reset=True)

import flask
import flask_jsglue
import flask_wtf
from wtforms import StringField
from wtforms.validators import InputRequired

application = flask.Flask(__name__)
application.config['TEST_SERVER_PORT'] = 9001
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
    form = RepoUrlForm()
    return flask.render_template('welcome.jinja', repo_url_form=form)


class Repo(object):
    def __init__(self, owner, name):
        self.owner = owner
        self.name = name

@application.route('/view-repo/<owner>/<repo_name>', methods=['GET'])
def view_repo(owner, repo_name):
    repository_url = 'https://api.github.com/repos/{}/{}'.format(owner, repo_name)
    gh_resp = requests.get('{0}/git/trees/master'.format(repository_url))
    master = gh_resp.json()
    gh_resp = requests.get(
        '{0}/git/trees/{1}'.format(repository_url, master['sha']),
        params={'recursive': 1})
    tree = gh_resp.json()
    repo = Repo(owner, repo_name)
    return flask.render_template('view-repo.jinja', tree=tree, repo=repo)


class RepoUrlForm(flask_wtf.FlaskForm):
    repo_url = StringField('Repository URL:', [InputRequired()])

@application.route('/view-repo-from-url', methods=['POST'])
def view_repo_from_url():
    # A sample repo-url:
    # https://github.com/allanderek/appraisal/
    form = RepoUrlForm(flask.request.form)
    if not form.validate():
        flask.flash('You must provide a github url')
        return flask.redirect(flask.url_for('homepage'))
    repo_url = form.repo_url.data
    fields = repo_url.split('/')
    try:
        github_com_index = fields.index('github.com')
    except ValueError:
        flask.flash('You must provide a github url')
        return flask.redirect(flask.url_for('homepage'))
    repo_owner, repo_name = fields[github_com_index + 1 : github_com_index + 3]
    if not repo_owner or not repo_name:
        flask.flash('Your github url must contain a repository own and repo name.')
        return flask.redirect(flask.url_for('homepage'))
    return flask.redirect(flask.url_for('view_repo', owner=repo_owner, repo_name=repo_name))


@application.route('/view-repo-report/<owner>/<repo_name>', methods=['GET'])
def view_repo_report(owner, repo_name):
    with orm.db_session:
        query = orm.select(
            a for a in Annotation
            if a.repo_owner == owner and
               a.repo == repo_name
            )
        annotations = list(query)
    repo = Repo(owner, repo_name)
    return flask.render_template('repo-report.jinja', annotations=annotations, repo=repo)


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

    with orm.db_session:
        annotations = [a.jsonify() for a in form.annotations_query()]
    return success_response(results={'annotations': annotations})

class SourceSpecifierForm(flask_wtf.FlaskForm):
    repo_owner = StringField('Repository Owner', [InputRequired()])
    repo = StringField('Repository', [InputRequired()])
    filepath = StringField('Filepath', [InputRequired()])

    def annotations_query(self):
        return orm.select(
            a for a in Annotation
            if a.repo_owner == self.repo_owner.data and
               a.repo == self.repo.data and
               a.filepath == self.filepath.data
            )


class AnnotationSpecifierForm(SourceSpecifierForm):
    line_number = StringField('Line number', [InputRequired()])

    def annotations_query(self):
        return orm.select(
            a for a in Annotation
            if a.repo_owner == self.repo_owner.data and
               a.repo == self.repo.data and
               a.filepath == self.filepath.data and
               a.line_number == self.line_number.data
            )

class AnnotationForm(AnnotationSpecifierForm):
    content = StringField('Content', [InputRequired()])


@application.route("/save-annotation", methods=['POST'])
def save_annotation():
    form = AnnotationForm(flask.request.form)
    if not form.validate():
        return bad_request_response(message='You must provide appropriate data.')

    with orm.db_session:
        annotation = Annotation.get(
            repo = form.repo.data,
            repo_owner = form.repo_owner.data,
            filepath = form.filepath.data,
            line_number = form.line_number.data,
            )
        if annotation:
            # For now assume one.
            annotation.content = form.content.data
        else:
            annotation = Annotation(
                repo = form.repo.data,
                repo_owner = form.repo_owner.data,
                filepath = form.filepath.data,
                line_number = form.line_number.data,
                content = form.content.data
                )
        orm.commit()
    return success_response()

@application.route("/delete-annotation", methods=['POST'])
def delete_annotation():
    form = AnnotationSpecifierForm(flask.request.form)

    if not form.validate():
        return bad_request_response(message='You must provide appropriate data.')

    with orm.db_session:
        annotation = Annotation.get(
            repo = form.repo.data,
            repo_owner = form.repo_owner.data,
            filepath = form.filepath.data,
            line_number = form.line_number.data,
            )
        if annotation:
            annotation.delete()
            orm.commit()
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
    set_database()
    application.run(
        port=8080,
        host='0.0.0.0',
        debug=True,
        extra_files=extra_files
        )


# Now for some testing.
from collections import OrderedDict
import logging
from selenium import webdriver
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, InvalidElementStateException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import pytest
# Currently just used for the temporary hack to quit the phantomjs process
# see below in quit_driver.
import signal

import threading
import wsgiref.simple_server

import unittest.mock as mock
import uuid

def get_new_unique_identifier():
    return uuid.uuid4().hex


def setup_testing(db_file='test.db'):
    reset = db_file == 'test.db'
    set_database(db_file=db_file, reset=reset)
    application.config['TESTING'] = True
    port = application.config['TEST_SERVER_PORT']
    application.config['SERVER_NAME'] = 'localhost:{}'.format(port)


class ServerThread(threading.Thread):
    def setup(self, db_file='test.db'):
        setup_testing(db_file=db_file)
        self.port = application.config['TEST_SERVER_PORT']

    def run(self):
        self.httpd = wsgiref.simple_server.make_server('localhost', self.port, application)
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()

class BrowserClient(object):
    """Interacts with a running instance of the application via animating a
    browser."""
    def __init__(self, db_file='test.db', browser="phantom",):
        self.server_thread = ServerThread()
        self.server_thread.setup(db_file=db_file)
        self.server_thread.start()

        driver_class = {
            'phantom': webdriver.PhantomJS,
            'chrome': webdriver.Chrome,
            'firefox': webdriver.Firefox
            }.get(browser)
        self.driver = driver_class()
        self.driver.set_window_size(1200, 760)
        # We may get rather a lot of noise with the selenium logger set to debug
        # so we set it to info instead.
        selenium_logger = logging.getLogger(name="selenium.webdriver.remote.remote_connection")
        selenium_logger.setLevel(logging.INFO)

        logfilename = generated_file_path('tests.log')
        logging.basicConfig(filename=logfilename)
        self.logger = logging.getLogger('browser-client')
        self.logger.setLevel(logging.INFO)

    def finalise(self):
        self.driver.close()
        # A bit of hack this but currently there is some bug I believe in
        # the phantomjs code rather than selenium, but in any case it means that
        # the phantomjs process is not being killed so we do so explicitly here
        # for the time being. Obviously we can remove this when that bug is
        # fixed. See: https://github.com/SeleniumHQ/selenium/issues/767
        self.driver.service.process.send_signal(signal.SIGTERM)
        self.driver.quit()

        self.server_thread.stop()
        self.server_thread.join()


    @property
    def page_source(self):
        return self.driver.page_source

    def log_current_page(self, message=None, output_basename=None):
        content = self.page_source
        if message:
            logging.info(message)
        # This is frequently what we really care about so I also output it
        # here as well to make it convenient to inspect (with highlighting).
        basename = output_basename or 'log-current-page'
        file_name = generated_file_path(basename + '.html')
        with open(file_name, 'w') as outfile:
            if message:
                outfile.write("<!-- {} --> ".format(message))
            outfile.write(content)
        filename = generated_file_path(basename + '.png')
        self.driver.save_screenshot(filename)

    def get_browser_log(self):
        # Note: this is mostly for debugging your tests. I have not used it
        # much and would expect this to change. We would probably like to
        # integrate this into 'log_current_page' somehow.
        log_name = 'har' # 'har' undocumented but returns more than 'browser'
        return client.driver.get_log(log_name)

    def visit_url(self, url):
        self.driver.get(url)

    def visit_view(self, *args, **kwargs):
        """ So you can say: `client.visit_view('homepage')`"""
        self.visit_url(make_url(*args, **kwargs))

    def scroll_to_element(self, element):
        self.driver.execute_script("return arguments[0].scrollIntoView();", element)

    def wait_for_condition(self, condition, timeout=5, failure_message=None):
        """Wait for the given condition and if it does not occur then log the
        the current page and fail the current test. If timeout is given then
        that is how long we wait.
        """
        wait = WebDriverWait(self.driver, timeout)
        try:
            element = wait.until(condition)
            return element
        except TimeoutException:
            self.log_current_page()
            message = failure_message or "Waiting on a condition timed out, current page logged."
            pytest.fail(message)

    def wait_for_element_to_be_clickable(self, selector, **kwargs):
        element_spec = (By.CSS_SELECTOR, selector)
        condition = expected_conditions.element_to_be_clickable(element_spec)
        return self.wait_for_condition(condition, **kwargs)

    def wait_for_element_to_be_visible(self, selector, **kwargs):
        element_spec = (By.CSS_SELECTOR, selector)
        condition = expected_conditions.visibility_of_element_located(element_spec)
        return self.wait_for_condition(condition, **kwargs)

    def wait_for_element_to_be_invisible(self, selector, **kwargs):
        element_spec = (By.CSS_SELECTOR, selector)
        condition = expected_conditions.invisibility_of_element_located(element_spec)
        return self.wait_for_condition(condition, **kwargs)

    def wait_for_element(self, selector, **kwargs):
        element_spec = (By.CSS_SELECTOR, selector)
        condition = expected_conditions.presence_of_element_located(element_spec)
        return self.wait_for_condition(condition, **kwargs)

    def css_exists(self, css_selector):
        """ Asserts that there is an element that matches the given
        css selector."""
        failure_message = 'Element "{0}" not found! Current page logged.'.format(css_selector)
        self.wait_for_element(css_selector, failure_message=failure_message)

    def check_css_selector_doesnt_exist(self, css_selector):
        """Assert that there is no element that matches the given css selector.
        Note that we do not use 'wait_for_element' since in that case a successful
        test woult take the whole timeout time."""
        try:
            self.driver.find_element_by_css_selector(css_selector)
        except NoSuchElementException:
            return
        self.log_current_page()
        pytest.fail("""Element "{0}" was found on page when expected not to be
        present. Current page logged.""".format(css_selector))

    def check_css_contains_texts(self, selector, *texts):
        """For each text argument given we check that there is an element
        matching the given selector which *contains* the given text. Note that
        it merely has to contain it, not equal it."""
        elements = self.driver.find_elements_by_css_selector(selector)
        element_texts = [e.text for e in elements]
        not_found = [t for t in texts if not any(t in et for et in element_texts)]
        if not_found:
            not_found_messages = ", ".join(not_found)
            self.log_current_page(message="Texts were not found: {}".format(not_found_messages))
            pytest.fail("""We expected elements with the following selector: {},
            to contain the following texts which were not found:
            "{}". Current page logged.""".format(selector, not_found_messages))

    def click(self, selector, **kwargs):
        """ Click an element given by the given selector. Passes its kwargs on
        to wait for element, so in particular accepts 'no_fail' which means the
        current test is not failed if the element does not exist (nor appear
        once waited upon).
        """
        try:
            if 'failure_message' not in kwargs:
                kwargs['failure_message'] = "Attempting to click element: {}".format(selector)
            element = self.wait_for_element(selector, **kwargs)
            self.scroll_to_element(element)
            self.wait_for_element_to_be_clickable(selector, **kwargs)
            element.click()
        except NoSuchElementException:
            if not kwargs.get('no_fail', False):
                self.log_current_page()
                pytest.fail('Element "{0}" not found! Current page logged.'.format(selector))
        except InvalidElementStateException as e:
            message = """Invalid state exception: {}.
            Current page logged.""".format(selector)
            self.log_current_page(message=message)
            pytest.fail(message + ": " + e.msg)

    def fill_in_input(self, form_element, input_name, input_text):
        # So note, in the case of radio buttons, all of the radio buttons will
        # match, so we then have to choose the one with the correct value. In
        # the case of a select we have even more work to do because we will have
        # to find the correct option element.
        input_css = 'input[name="{0}"],textarea[name="{0}"],select[name="{0}"]'.format( input_name)
        # We cannot just search for the input-css because in the case of a radio
        # button there will be more than one of them. So we eliminate any of the
        # matching input_elements that have a value defined but it is not the
        # value that we wish to enter.
        # However, note that in the case that we are 'Editing' an input field
        # may have a 'value' attribute that is not the same as 'input_text'.
        # We probably still could do this via CSS with something like:
        # 'input[type="radio", value=#{input_text}], input[type="text"]'
        # But it would be quite long as we would have to enumerate all of the
        # input types for which we expect the value to be different, text, url,
        # email etc.
        def appropriate_input(element):
            return (element.get_attribute('type') != 'radio' or
                    element.get_attribute('value') == input_text)
        input_element = next(e for e in form_element.find_elements_by_css_selector(input_css)
                             if appropriate_input(e))
        if input_element is None:
            pytest.fail("Input element is None: {} - {}".format(input_name, input_text))

        input_type = input_element.get_attribute("type")
        if input_type == 'hidden':
            # Then it should already have the correct value and we do not
            # wish to manipulate it. The value is probably in an input
            # dictionary for the app-client.
            return

        self.scroll_to_element(input_element)
        # If the input element is not displayed then we skip over it, this
        # likely means that the input is only appropriate if a certain radio or
        # checkbox item is displayed. However, also note that this means we must
        # make sure that the checkbox/radio input is done before the corresponding
        # extra-inputs.
        if not input_element.is_displayed():
            logging.info("Element {} not displayed therefore not filled in.")
            # It's a slight hack to include the case in which the current value
            # is the same as the desired one, we could get rid of this after the
            # add_channel is no longer needed (in favour of two propose channels)
            if input_text and input_element.get_attribute('value') != input_text:
                message = """Element is not displayed and cannot have input
                given to it: {} - {}""".format(input_name, input_text)
                self.log_current_page(message=message)
                pytest.fail(message)
            return
        try:
            if input_type == "checkbox" and input_text or input_type == 'radio':
                input_element.click()
            # TODO: Not sure how should I uncheck a previously checked field?
            elif input_type == "checkbox" and not input_text:
                pass
            elif input_element.tag_name == 'select':
                # In the case of a select element we have to click the
                # appropriate option, I'm not sure how well this will work in
                # the case that it has to scroll through the list of options.
                option_css = 'option[value="{0}"]'.format(input_text)
                option_element = input_element.find_element_by_css_selector(option_css)
                option_element.click()
            elif input_type in ['text', 'textarea', 'password', 'email', 'url']:
                input_element.clear()
                # Note: this means that if you provide an empty field eg.
                # 'middle_name': ''
                # In your data, then it will have the input field *cleared*, if
                # you wish for it to simply remain the same, then you should not
                # have it in your data at all.
                if input_text:
                    input_element.send_keys(input_text)
            elif input_type == 'submit':
                # Right this means that if the input is 'True' then we are
                # submitting this form by clicking the relevant submit button.
                # If the input is 'False' that probably means there is more
                # than one submit button, corresponding to different responses,
                # such as 'Allow'/'Deny', or 'Approve'/'Reject'.
                if input_text and input_text != 'n':
                    input_element.click()
            else:
                pytest.fail("Unknown input type: {}, for input: {}".format(input_type, input_name))
        except InvalidElementStateException as e:
            message = """Invalid state exception: {} - {}.
            Current page logged.""".format(input_name, input_text)
            self.log_current_page(message=message)
            pytest.fail(message + ": " + e.msg)

    def fill_in_text_input_by_css(self, input_css, input_text, clear=False):
        input_element = self.driver.find_element_by_css_selector(input_css)
        if clear:
            input_element.clear()
        input_element.send_keys(input_text)


    def fill_in_form(self, form_selector, fields):
        """ form_selector should be the css used to identify the form. fields
        will be a dictionary mapping field names to the values you wish to input
        whether that be text or, for example, the value to select from a select
        field. This will submit the form, if one of the inputs happens to be of
        type 'submit'. If you want the form fields to be input in a specific
        order (and if one of the inputs is a 'submit' field then you probably
        want that to be last), you should use an 'OrderedDict' for the fields.
        """
        try:
            form_element = self.driver.find_element_by_css_selector(form_selector)
        except NoSuchElementException:
            self.log_current_page()
            pytest.fail("""Attempt to fill in a form we could not find: "{0}"
            Current page logged.""".format(form_selector))
        for field_name, field_value in fields.items():
            self.fill_in_input(form_element, field_name, field_value)


def make_url(endpoint, **kwargs):
    with application.app_context():
        return flask.url_for(endpoint, **kwargs)

@pytest.fixture(scope='module')
def client(request):
    options = ['db_file', 'browser']
    kwargs = {k: request.config.getoption('--{}'.format(k), None) for k in options}
    kwargs = {k:v for k,v in kwargs.items() if v is not None}
    client = BrowserClient(**kwargs)
    request.addfinalizer(client.finalise)
    return client

def check_view_repository(client, repo_owner, repo):
    repo_url = 'https://github.com/{}/{}'.format(repo_owner, repo)
    form_input = OrderedDict(repo_url = repo_url)
    form_input['submit'] = True
    form_selector = '#view-repo-form'
    client.fill_in_form(form_selector, form_input)

class AnnotDesc(object):
    """This is used to store the description of an annotation during testing,
    it is *not* stored (at least not directly) in the database. The whole point
    is that we check the application is storing the equivalent annotation in the
    database (or we check that it is *not* if that is the behaviour we want such
    as for a deleted annotation)."""
    def __init__(self, content, line_number):
        self.content = content
        self.line_number = line_number
        self.code_line_id = "code-line-{}".format(line_number)

    def create_annotation(self, client):
        client.click('#{}.code-line-container'.format(self.code_line_id))
        # So note in particular we are *not* sending the keys to the specific annotation
        # text input, since we are testing that creating an annotation should automatically
        # give the focus to the annotation's input box.
        ActionChains(client.driver).send_keys(self.content).perform()

        # This is to force the annotation to be saved by removing the focus from the
        # annotation input. TODO: Obviously this would only work for the browser-client
        # I don't know if perhaps an ApplicationClient should just mimic the selenium
        # ActionChains protocol?
        ActionChains(client.driver).key_down(Keys.CONTROL).key_up(Keys.CONTROL).perform()

    def update_annotation(self, client, new_text, clear=True):
        self.content = new_text
        input_css = '.annotation[code-line="{}"] .annotation-input'.format(self.code_line_id)
        client.fill_in_text_input_by_css(input_css, new_text, clear=clear)
        ActionChains(client.driver).key_down(Keys.CONTROL).key_up(Keys.CONTROL).perform()

    def get_db_annotation(self, **kwargs):
        with orm.db_session:
            defaults = dict(content=self.content, line_number=self.code_line_id)
            defaults.update(kwargs)
            db_annotation = Annotation.get(**defaults)
        return db_annotation

def click_source_file(client, filepath):
    css = '.source-file-link[path="{}"]'.format(filepath)
    client.click(css)


def test_main(client):
    client.logger.info('Visit the homepage')
    client.visit_view('homepage')
    assert 'Welcome to Appraisal Board' in client.page_source

    repo_owner = 'kennethreitz'
    repo = 'requests'
    filepath = 'setup.py'
    check_view_repository(client, repo_owner, repo)

    client.logger.info('Click on the first source file link to view source')
    click_source_file(client, filepath)

    client.logger.info('Click on a source file line to create an annotation')
    client.click('.code-line-container')
    client.css_exists('.annotation')
    client.logger.info("""Fill in the text of the annotation and check that it \
    and check that it exists in the database.""")
    first_text = 'Here I am to save the day.'
    annotation = AnnotDesc(first_text, '3')
    annotation.create_annotation(client)
    assert annotation.get_db_annotation(
        repo = repo,
        repo_owner = repo_owner,
        filepath = filepath
        )

    client.logger.info("Refresh this page and check that the annotation is still there.")
    client.visit_view('view_source', repo=repo, owner=repo_owner, filepath=filepath)
    client.css_exists('.annotation')

    client.logger.info("""Update the annotation, and check that we do not have two
    annotations in the database.""")
    new_annotation_text = 'Stand back, I know regular expressions'
    client.log_current_page()
    annotation.update_annotation(client, new_annotation_text)
    assert annotation.get_db_annotation(
        repo = repo,
        repo_owner = repo_owner,
        filepath = filepath
        )
    assert not annotation.get_db_annotation(
        # There should not be 'second' annotation with the orignal text.
        content = first_text,
        repo = repo,
        repo_owner = repo_owner,
        filepath = filepath
        )

    client.logger.info('Delete the annotation and check that it is not in the database.')
    client.click('.delete-annotation')
    db_annotation = annotation.get_db_annotation(
        repo = repo,
        repo_owner = repo_owner,
        filepath = filepath
        )
    assert db_annotation is None


def test_report(client):
    repo = 'appraisal'
    repo_owner = 'allanderek'

    client.logger.info('Visit the homepage')
    client.visit_view('homepage')
    assert 'Welcome to Appraisal Board' in client.page_source

    check_view_repository(client, repo_owner, repo)

    client.logger.info('Click on source file link for "main.py".')
    main_filepath = 'main.py'
    click_source_file(client, main_filepath)

    client.logger.info('Create a couple of annotations.')
    main_annotations = [
        AnnotDesc('This is line number 3', '3'),
        AnnotDesc('This is line number 5', '5')
        ]
    for annotation in main_annotations:
        annotation.create_annotation(client)


    client.logger.info('Click on the link to go back upwards to the containing directory')
    client.click('#view-repo')

    client.logger.info('Click on the link to view the templates/base.jinja source.')
    base_template_filepath = 'templates/base.jinja'
    click_source_file(client, base_template_filepath)

    client.logger.info('Create a couple more annotations')
    base_template_annotations = [
        AnnotDesc('This is line number 8', '8'),
        AnnotDesc('This is line number 10', '10')
        ]
    for annotation in base_template_annotations:
        annotation.create_annotation(client)

    client.logger.info('Click on view report link for this repository')
    client.click('#view-report')

    client.logger.info('Check that the report has all four annotations that we have created.')
    contents = [a.content for a in main_annotations + base_template_annotations]
    client.check_css_contains_texts('.annotation', *contents)

@appraisal.command(
    'test',
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True)
    )
@click.pass_context
def my_test_command(context):
    """This is the command to run in order to simply run the test suite.
    Called from the command-line as `python main.py test`, the function is
    named like this to avoid a spurious warning from pytest. We also accept
    additional arguments which are passed through to pytest, for example if you
    wish to run only tests which have 'report' in their name you can do:
    'python main.py test -k report'
    or if you wish to show the locals in a traceback:
    'python main.py test -l'
    You can get more information on the arguments you can pass to pytest with:
    'py.test --help'
    """
    command = ['main.py', '--cov=.', '--cov-report=html']
    if not any('maxfail' in a for a in context.args):
        command.append('--maxfail=1')
    for item in context.args:
        command.append(item)
    pytest.main(command)

@appraisal.command()
def flake8():
    """Simply run this command to check the source code."""
    os.system('flake8 main.py')

if __name__ == '__main__':
    appraisal()
