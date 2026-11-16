"""Offline notebook compatibility and redirect checks; no kernels or remote requests."""

import importlib.metadata
import unittest

import nbformat
from bs4 import BeautifulSoup
from nbconvert import HTMLExporter
from packaging.version import Version
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application, RedirectHandler


class NotebookParsingTests(unittest.TestCase):
    def test_installed_security_baseline(self):
        for name, minimum in (("soupsieve", "4.0"), ("tornado", "6.6.1")):
            with self.subTest(package=name):
                self.assertGreaterEqual(Version(importlib.metadata.version(name)), Version(minimum))

    def test_notebook_imports(self):
        import ipykernel
        import jupyterlab
        import notebook

        for module in (ipykernel, jupyterlab, notebook):
            self.assertEqual(module.__version__, importlib.metadata.version(module.__name__))

    def test_descendant_selectors_and_dom_changes(self):
        # Small bounded markup exercises cached descendant matching without a timing/load test.
        soup = BeautifulSoup(
            '<section><div><div class="result">kept</div></div></section>'
            + '<div>' * 24 + 'outside' + '</div>' * 24,
            "html.parser",
        )
        self.assertEqual([node.text for node in soup.select("section div div.result")], ["kept"])
        self.assertEqual(soup.select("article div div"), [])
        soup.section.name = "article"
        self.assertEqual(soup.select("section div div.result"), [])
        self.assertEqual(soup.select_one("article div div.result").text, "kept")

    def test_nbconvert_html_export(self):
        notebook = nbformat.v4.new_notebook(cells=[
            nbformat.v4.new_markdown_cell("# Local notebook fixture\n\n**rendered text**"),
            nbformat.v4.new_code_cell("1 + 1", outputs=[
                nbformat.v4.new_output("execute_result", data={"text/plain": "2"}, execution_count=1),
            ], execution_count=1),
        ])
        body, _ = HTMLExporter(template_name="lab").from_notebook_node(notebook)
        soup = BeautifulSoup(body, "html.parser")
        self.assertEqual(soup.select_one("h1").get_text(strip=True).rstrip("¶"), "Local notebook fixture")
        self.assertEqual(soup.select_one("strong").text, "rendered text")
        self.assertIn("2", soup.select_one(".jp-OutputArea-output").text)


class NotebookRedirectTests(AsyncHTTPTestCase):
    def get_app(self):
        return Application([
            (r"/redirect/(.*)", RedirectHandler, {"url": "/{0}/view"}),
            # A trusted fixed URL with no substitutions remains supported in 6.6.1.
            (r"/fixed", RedirectHandler, {"url": "https://example.invalid/docs"}),
        ])

    def test_substitutions_cannot_change_redirect_host(self):
        for value in ("/example.invalid", "//example.invalid", "///example.invalid"):
            with self.subTest(value=value):
                response = self.fetch("/redirect/" + value, follow_redirects=False)
                self.assertEqual(response.code, 400)
                self.assertNotIn("Location", response.headers)

    def test_local_redirect_keeps_query(self):
        response = self.fetch("/redirect/notebook?download=1", follow_redirects=False)
        self.assertEqual(response.code, 301)
        self.assertEqual(response.headers["Location"], "/notebook/view?download=1")

    def test_trusted_fixed_url_is_preserved_without_following(self):
        response = self.fetch("/fixed", follow_redirects=False)
        self.assertEqual(response.code, 301)
        self.assertEqual(response.headers["Location"], "https://example.invalid/docs")


if __name__ == "__main__":
    unittest.main()
