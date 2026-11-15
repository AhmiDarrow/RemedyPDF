"""Keep the UI language on English around every test.

Pytest must not read or write the user's RemedyPDF profile. ``init_i18n``
with no ``--home`` and no explicit language does that while a test is running.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _english_locale():
    from i18n import init_i18n, set_language

    init_i18n(["remedypdf"])
    set_language("en", persist=False)
    yield
    init_i18n(["remedypdf"])
    set_language("en", persist=False)
