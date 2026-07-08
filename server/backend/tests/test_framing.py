from app.protocol.framing import FrameAccumulator, encode_frame


def test_encode_frame_ends_with_zero_and_has_no_inner_zero():
    frame = encode_frame(b"\x01\x02\x00\x03")
    assert frame[-1] == 0
    assert 0 not in frame[:-1]


def test_feed_single_complete_frame():
    acc = FrameAccumulator()
    assert acc.feed(encode_frame(b"abc")) == [b"abc"]


def test_feed_split_across_chunks():
    acc = FrameAccumulator()
    frame = encode_frame(b"\x10\x00\x20")
    assert acc.feed(frame[:2]) == []
    assert acc.feed(frame[2:]) == [b"\x10\x00\x20"]


def test_feed_multiple_frames_in_one_chunk():
    acc = FrameAccumulator()
    chunk = encode_frame(b"one") + encode_frame(b"two")
    assert acc.feed(chunk) == [b"one", b"two"]


def test_corrupt_frame_is_dropped_and_stream_continues():
    acc = FrameAccumulator()
    bad = b"\x05\x11\x22\x00"  # 잘린 COBS 블록 + 구분자
    out = acc.feed(bad + encode_frame(b"ok"))
    assert out == [b"ok"]


def test_empty_frame_ignored():
    acc = FrameAccumulator()
    assert acc.feed(b"\x00\x00") == []
