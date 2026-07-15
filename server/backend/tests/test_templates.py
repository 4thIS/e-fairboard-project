from app.protocol.templates import TEMPLATES, as_dict, field_avail_w


def test_templates_defined():
    assert set(TEMPLATES.keys()) == {0, 1, 2, 3, 4}


def test_field_ids_match_protocol_spec():
    # PROTOCOL.md §8: 행사 안내(0)=4, 부스 지도(1)=2, 모집 공고(2)=3, 일정표(3)=4
    # + 팀 소개(4)=4 (세로, PROTOCOL.md 반영은 준표와 협의 — 스펙 §Global Constraints)
    assert [len(TEMPLATES[i].fields) for i in range(5)] == [4, 2, 3, 4, 4]
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
            avail = field_avail_w(f, tpl.qr, tpl.canvas_w)
            width = (f.max_bytes // 3) * f.font_size
            assert width <= avail, (
                f"{tpl.name}/{f.name}: {f.max_bytes}B → {width}px > 가용 {avail}px")


def test_geometry_inside_each_templates_canvas():
    for tpl in TEMPLATES.values():
        w, h = tpl.canvas_w, tpl.canvas_h
        for f in tpl.fields:
            assert 0 <= f.x < w and 0 <= f.y < h, f"{tpl.name}/{f.name}"
        assert tpl.qr.x + tpl.qr.size <= w and tpl.qr.y + tpl.qr.size <= h, tpl.name


def test_as_dict_is_json_shape():
    data = as_dict()
    assert len(data) == 5
    assert data[0]["fields"][0]["name"]
    assert {"x", "y", "size"} <= set(data[0]["qr"].keys())


def test_field_avail_w_shrinks_only_for_rows_overlapping_qr():
    tpl = TEMPLATES[0]  # 행사 안내, QR(224, 32, 64)
    title, when = tpl.fields[0], tpl.fields[1]
    # 제목 y=8, 16px → 8~24. QR은 y 32~96 → 안 겹침 → 캔버스 끝까지
    assert field_avail_w(title, tpl.qr, tpl.canvas_w) == 296 - 8
    # 일시 y=48, 16px → 48~64. QR과 겹침 → QR 앞까지
    assert field_avail_w(when, tpl.qr, tpl.canvas_w) == 224 - 8


def test_template3_qr_is_higher_so_different_rows_overlap():
    tpl = TEMPLATES[3]  # 일정표, QR(240, 8, 48) → y 8~56
    date, s1, s2 = tpl.fields[0], tpl.fields[1], tpl.fields[2]
    assert field_avail_w(date, tpl.qr, tpl.canvas_w) == 240 - 8   # y 8~24  겹침
    assert field_avail_w(s1, tpl.qr, tpl.canvas_w) == 240 - 8     # y 44~60 겹침
    assert field_avail_w(s2, tpl.qr, tpl.canvas_w) == 296 - 8     # y 72~88 안 겹침


def test_as_dict_carries_avail_w():
    data = as_dict()
    fields = data[0]["fields"]
    assert fields[0]["avail_w"] == 288
    assert fields[1]["avail_w"] == 216


def test_template_carries_its_own_canvas():
    # 기존 가로 템플릿은 296×128 기본값 그대로
    assert (TEMPLATES[0].canvas_w, TEMPLATES[0].canvas_h) == (296, 128)


def test_field_avail_w_uses_the_given_canvas_not_a_global():
    """세로 캔버스(128)에서 296 이 새어 들어오면 미리보기가 거짓말을 한다."""
    tpl = TEMPLATES[0]
    f = tpl.fields[0]  # 제목 x=8, y=8 — QR(224,32,64)과 안 겹침
    assert field_avail_w(f, tpl.qr, 296) == 288
    assert field_avail_w(f, tpl.qr, 128) == 120   # 캔버스가 좁으면 가용 폭도 좁다


def test_as_dict_carries_canvas():
    data = as_dict()
    assert data[0]["canvas"] == {"w": 296, "h": 128}


def test_portrait_template_is_128x296():
    tpl = TEMPLATES[4]
    assert (tpl.canvas_w, tpl.canvas_h) == (128, 296)
    assert tpl.name == "팀 소개"


def test_portrait_fields_are_all_16px():
    # 32px 한글은 폭 120px 안에 3자만 들어간다 — 한글 팀명이 잘린다 (스펙 §2)
    assert all(f.font_size == 16 for f in TEMPLATES[4].fields)


def test_portrait_avail_w_is_the_narrow_canvas():
    tpl = TEMPLATES[4]
    # QR(y 140~235)과 세로로 겹치는 필드가 없다 → 모든 행이 캔버스 끝(128)까지
    for f in tpl.fields:
        assert field_avail_w(f, tpl.qr, tpl.canvas_w) == 120, f.name
