import pytest


def pytest_addoption(parser):
    parser.addoption("--browser-tests", action="store_true", help="Run Chromium mobile integration tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "browser: real Chromium tests requiring Playwright and its browser")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--browser-tests"):
        for item in items:
            if "browser" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Use --browser-tests to run browser integration tests"))
