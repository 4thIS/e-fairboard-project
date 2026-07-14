from app.protocol.templates import TEMPLATES, as_dict


def test_four_templates_defined():
    assert set(TEMPLATES.keys()) == {0, 1, 2, 3}


def test_field_ids_match_protocol_spec():
    # PROTOCOL.md §8: 행사 안내(0)=필드 4개, 부스 지도(1)=2, 모집 공고(2)=3, 일정표(3)=4
    assert [len(TEMPLATES[i].fields) for i in range(4)] == [4, 2, 3, 4]
    for tpl in TEMPLATES.values():
        assert [f.id for f in tpl.fields] == list(range(len(tpl.fields)))


def test_max_bytes_fits_set_field_payload():
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert 0 < f.max_bytes <= 198  # SET_FIELD text 한도 (200-2)


def test_font_size_is_16_or_32():
    # 노드 폰트가 16×16 비트맵이라 정수 배율만 가능하다 (이슈 #12).
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert f.font_size in (16, 32), f"{tpl.name}/{f.name} = {f.font_size}px"


def test_max_bytes_fits_screen_width():
    """max_bytes 는 페이로드가 아니라 화면 폭에서 나온다 (이슈 #12).

    한글 1자 = font_size px = 3B. QR 박스와 y 가 겹치는 행은 폭이 QR.x 까지로 줄어든다.
    ASCII 는 반각(font_size/2 px)이라 바이트당 폭이 한글보다 넓지만, 그건 노드 렌더러가
    픽셀 폭으로 잘라 막는다 — 여기서는 한글 최악 기준만 본다.
    """
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            overlaps_qr = f.y < tpl.qr.y + tpl.qr.size and tpl.qr.y < f.y + f.font_size
            avail = (tpl.qr.x if overlaps_qr else 296) - f.x
            width = (f.max_bytes // 3) * f.font_size  # 한글 최악
            assert width <= avail, (
                f"{tpl.name}/{f.name}: {f.max_bytes}B → {width}px > 가용 {avail}px")


def test_geometry_inside_296x128():
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert 0 <= f.x < 296 and 0 <= f.y < 128
        assert tpl.qr.x + tpl.qr.size <= 296 and tpl.qr.y + tpl.qr.size <= 128


def test_as_dict_is_json_shape():
    data = as_dict()
    assert len(data) == 4
    assert data[0]["fields"][0]["name"]
    assert {"x", "y", "size"} <= set(data[0]["qr"].keys())
