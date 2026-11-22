import smartevse


def test_version_is_a_non_empty_string():
    assert isinstance(smartevse.__version__, str) and smartevse.__version__
