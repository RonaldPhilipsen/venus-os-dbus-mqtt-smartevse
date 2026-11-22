import re

import smartevse


def test_version_has_the_release_format():
    # scripts/build-zip.sh accepts the same characters.
    assert re.fullmatch(r"[0-9A-Za-z.+-]+", smartevse.__version__)
