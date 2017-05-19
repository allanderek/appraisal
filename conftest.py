import pytest

def pytest_addoption(parser):
    parser.addoption("--mock-github", action="store", default=True,
        help="Whether or not we mock the github-api.")
    parser.addoption("--browser", action="store", default="phantom",
        help="Set which browser driver to use in the browser tests, chrome or firefox, default is phantom")
    parser.addoption("--db_file", action="store", default="test.db",
        help="db file, generally set it to 'play.db' or 'test.db'")
