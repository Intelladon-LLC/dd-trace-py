import os

import pytest

from ddtrace import Pin
from ddtrace.ext import test

from ... import TracerTestCase


class TestPytest(TracerTestCase):
    @pytest.fixture(autouse=True)
    def initdir(self, testdir):
        self.testdir = testdir

    def inline_run(self, *args):
        """Execute test script with test tracer."""

        class PinTracer:
            @staticmethod
            def pytest_configure(config):
                Pin.override(config, tracer=self.tracer)

        return self.testdir.inline_run(*args, plugins=[PinTracer()])

    def test_parameterize_case(self):
        """Test parametrize case."""
        py_file = self.testdir.makepyfile(
            """
            import pytest

            @pytest.mark.parametrize('abc', [1, 2, 3, 4, pytest.param(5, marks=pytest.mark.skip)])
            class Test1(object):
                def test_1(self, abc):
                    assert abc in {1, 2, 3}
        """
        )
        file_name = os.path.basename(py_file.strpath)
        rec = self.inline_run("--ddtrace", file_name)
        rec.assertoutcome(passed=3, failed=1, skipped=1)
        spans = self.tracer.writer.pop()

        assert len(spans) == 5

    def test_skip(self):
        """Test parametrize case."""
        py_file = self.testdir.makepyfile(
            """
            import pytest

            @pytest.mark.skip(reason="decorator")
            def test_decorator():
                pass

            def test_body():
                pytest.skip("body")
        """
        )
        file_name = os.path.basename(py_file.strpath)
        rec = self.inline_run("--ddtrace", file_name)
        rec.assertoutcome(skipped=2)
        spans = self.tracer.writer.pop()

        assert len(spans) == 2
        assert spans[0].get_tag(test.STATUS) == test.Status.SKIP.value
        assert spans[0].get_tag(test.SKIP_REASON) == "decorator"
        assert spans[1].get_tag(test.STATUS) == test.Status.SKIP.value
        assert spans[1].get_tag(test.SKIP_REASON) == "body"

    def test_fixture(self):
        """Test ddspan fixture."""
        py_file = self.testdir.makepyfile(
            """
            import pytest

            def test_fixture(ddspan):
                assert ddspan is not None
                ddspan.set_tag("world", "hello")
        """
        )
        file_name = os.path.basename(py_file.strpath)
        rec = self.inline_run("--ddtrace", file_name)
        rec.assertoutcome(passed=1)
        spans = self.tracer.writer.pop()

        assert len(spans) == 1
        assert spans[0].get_tag("world") == "hello"
        assert spans[0].get_tag(test.STATUS) == test.Status.PASS.value