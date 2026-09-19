"""Shared guards for the scraper test suite."""

from __future__ import annotations

import pytest

from scraper import build as build_module


@pytest.fixture(autouse=True)
def committed_files_are_never_written():
    """Fail any test that writes a committed data file.

    ``build()`` defaults several paths to the real files in ``data/``.  A test
    that forgets to override one writes the maintainer's data — worst of all
    ``data/id-registry.json``, which is append-only and committed, so a stray
    fixture model would burn a permanent ID.
    """
    guarded = [
        build_module.REGISTRY_PATH,   # append-only; a stray fixture burns an ID
        build_module.DATA_JS_PATH,    # the committed build output
        build_module.RAW_LOCAL,       # hand-curated, highest-authority data
    ]
    # mtime as well as content: an atomic rewrite with identical bytes is still
    # a write, and the next fixture that differs would land on the real file.
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in guarded if path.exists()
    }

    yield

    for path in guarded:
        if path not in before:
            assert not path.exists(), (
                f"test created the committed file {path} — "
                f"pass an explicit tmp_path for it to build()"
            )
            continue
        content, mtime = before[path]
        assert (path.read_bytes(), path.stat().st_mtime_ns) == (content, mtime), (
            f"test wrote to the committed file {path} — "
            f"pass an explicit tmp_path for it to build()"
        )
