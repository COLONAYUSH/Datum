"""Tests for L0 object storage. No external service needed -- pure
filesystem, so these always run.
"""

from __future__ import annotations

import hashlib

import pytest

from datum.storage.blobstore import (
    InvalidContentHashError,
    LocalFilesystemBlobStore,
    content_hash,
)


@pytest.fixture
def store(tmp_path):
    return LocalFilesystemBlobStore(tmp_path / "blobs")


def test_put_returns_sha256_of_bytes(store):
    data = b"hello datum"
    got = store.put(data)
    assert got == hashlib.sha256(data).hexdigest()


def test_content_hash_helper_matches_put(store):
    data = b"some raw source material"
    assert store.put(data) == content_hash(data)


def test_round_trip_get_after_put(store):
    data = b"a document's raw bytes"
    h = store.put(data)
    assert store.get(h) == data


def test_exists_false_before_put_true_after(store):
    data = b"exists probe"
    h = content_hash(data)
    assert store.exists(h) is False
    store.put(data)
    assert store.exists(h) is True


def test_put_is_idempotent_same_bytes_twice_is_a_no_op(store):
    data = b"idempotent write"
    h1 = store.put(data)
    h2 = store.put(data)
    assert h1 == h2
    assert store.get(h1) == data


def test_sharded_by_first_two_hex_chars(store, tmp_path):
    data = b"shard probe"
    h = store.put(data)
    shard_dir = tmp_path / "blobs" / h[:2]
    assert (shard_dir / h).is_file()


def test_no_leftover_tmp_files_after_put(store, tmp_path):
    store.put(b"leftover probe")
    tmp_files = list((tmp_path / "blobs").rglob("*.tmp"))
    assert tmp_files == []


def test_different_bytes_get_different_hashes(store):
    h1 = store.put(b"content A")
    h2 = store.put(b"content B")
    assert h1 != h2


def test_get_missing_hash_raises_file_not_found(store):
    fake_hash = "0" * 64
    with pytest.raises(FileNotFoundError):
        store.get(fake_hash)


@pytest.mark.parametrize(
    "bad_hash",
    [
        "../../../etc/passwd",
        "not-hex-at-all",
        "abc",  # too short
        "g" * 64,  # not hex
        "A" * 64,  # uppercase, not accepted -- lowercase hex only
        "",
    ],
)
def test_get_rejects_malformed_hash_before_touching_filesystem(store, bad_hash):
    with pytest.raises(InvalidContentHashError):
        store.get(bad_hash)


@pytest.mark.parametrize("bad_hash", ["../escape", "..", "/etc/passwd", ""])
def test_exists_rejects_malformed_hash(store, bad_hash):
    with pytest.raises(InvalidContentHashError):
        store.exists(bad_hash)


def test_root_directory_created_on_construction(tmp_path):
    root = tmp_path / "nested" / "blobs"
    assert not root.exists()
    LocalFilesystemBlobStore(root)
    assert root.is_dir()
