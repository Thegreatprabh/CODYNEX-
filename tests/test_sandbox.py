"""Sandbox tests: patch parsing, application, and pytest runs."""
import os
import textwrap

import pytest

from dna.verify import sandbox as sb
from tests import FIXTURE

# A patch that changes checkout's docstring (tests still pass)
GOOD_PATCH = textwrap.dedent("""\
    --- a/service.py
    +++ b/service.py
    @@ -11,5 +11,5 @@
     def checkout(user, total):
    -    \"\"\"Run a checkout: builds an order and a receipt slug.\"\"\"
    +    \"\"\"Run a checkout: builds an order and a receipt slug. (v2)\"\"\"
         order = Order(order_id=1, user=user, total=total)
         receipt = slugify(user.name) + "-" + money(total)
         return order, receipt
    """)

# A patch that swaps name/email in create_user (test_create_user fails)
BREAKING_PATCH = textwrap.dedent("""\
    --- a/service.py
    +++ b/service.py
    @@ -6,3 +6,3 @@
     def create_user(name, email):
         \"\"\"Create a new user.\"\"\"
    -    return User(name=name, email=email)
    +    return User(name=email, email=name)
    """)


def test_parse_diff_good():
    files = sb.parse_diff(GOOD_PATCH)
    assert len(files) == 1
    path, hunks = files[0]
    assert path == "service.py"
    assert len(hunks) == 1
    old_start, old_block, new_block = hunks[0]
    assert old_start == 11
    assert old_block[1].startswith('    """Run a checkout')
    assert "(v2)" in new_block[1]
    assert len(old_block) == len(new_block) == 5


def test_parse_diff_malformed():
    with pytest.raises(ValueError):
        sb.parse_diff("this is not a diff\n")
    files, err = sb.apply_patch("/tmp", "garbage")
    assert files == [] and err


def test_apply_patch(tmp_path):
    target = tmp_path / "f.py"
    target.write_text("a\nb\nc\nd\n")
    diff = ("--- a/f.py\n+++ b/f.py\n"
            "@@ -1,4 +1,4 @@\n a\n-b\n+B!\n c\n d\n")
    patched, err = sb.apply_patch(str(tmp_path), diff)
    assert err == ""
    assert patched == ["f.py"]
    assert target.read_text() == "a\nB!\nc\nd\n"


def test_apply_patch_context_mismatch(tmp_path):
    target = tmp_path / "f.py"
    target.write_text("a\nb\nc\nd\n")
    # claims line 2 is "X" but it's "b" → must refuse
    diff = ("--- a/f.py\n+++ b/f.py\n"
            "@@ -1,4 +1,4 @@\n a\n-X\n+X!\n c\n d\n")
    patched, err = sb.apply_patch(str(tmp_path), diff)
    assert patched == []
    assert "mismatch" in err
    assert target.read_text() == "a\nb\nc\nd\n"  # untouched


def test_apply_patch_missing_target(tmp_path):
    diff = "--- a/nope.py\n+++ b/nope.py\n@@ -1 +1 @@\n-a\n+b\n"
    patched, err = sb.apply_patch(str(tmp_path), diff)
    assert patched == []
    assert "not found" in err


def test_verify_good_patch():
    res = sb.verify_patch(FIXTURE, GOOD_PATCH, timeout=60)
    assert res.patch_error == ""
    assert res.applied
    assert res.files_patched == ["service.py"]
    assert res.tests_ran and not res.timed_out
    assert res.passed, res.output_tail  # fixture tests still green


def test_verify_breaking_patch():
    res = sb.verify_patch(FIXTURE, BREAKING_PATCH, timeout=60)
    assert res.applied, res.patch_error
    assert res.tests_ran
    assert not res.passed
    assert res.failed_count >= 1


def test_copy_skips_junk(tmp_path):
    src = tmp_path / "proj"
    (src / ".git").mkdir(parents=True)
    (src / "__pycache__").mkdir()
    (src / ".git" / "x").write_text("junk")
    (src / "ok.py").write_text("x=1\n")
    dst = tmp_path / "dst"
    dst.mkdir()
    sb._copy_tree(str(src), str(dst))
    assert (dst / "ok.py").exists()
    assert not (dst / ".git").exists()
    assert not (dst / "__pycache__").exists()
