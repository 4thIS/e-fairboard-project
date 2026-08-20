from app.protocol.templates import FieldDef, QrDef, TEMPLATES, as_dict, field_avail_w


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


def test_font_size_is_sane_pixel_height():
    # font_size 는 실제 px 높이 (노드 stb_truetype native 래스터, 폰트 렌더 V2).
    # 정수 배율 제약은 없앴다 — 읽히는 최소·버퍼 안전 상한만 지킨다.
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert 16 <= f.font_size <= 256, \
                f"{tpl.name}/{f.name} = {f.font_size}px"


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


def test_field_avail_w_shrinks_for_overlapping_row_only():
    """field_avail_w 자체 검증 — 템플릿 레이아웃과 무관한 합성 케이스.
    (실제 800×480 템플릿은 QR을 구석에 둬 겹치는 행이 없다.)"""
    qr = QrDef(x=616, y=296, size=160)   # y 296~456
    over = FieldDef(0, "over", 24, 300, 32, 1)    # y 300~332 → QR과 겹침
    clear = FieldDef(1, "clear", 24, 32, 48, 1)   # y 32~80 → 안 겹침
    assert field_avail_w(over, qr, 800) == 616 - 24    # QR 앞까지
    assert field_avail_w(clear, qr, 800) == 800 - 24   # 캔버스 끝까지


def test_as_dict_carries_avail_w():
    data = as_dict()
    fields = data[0]["fields"]
    assert fields[0]["avail_w"] == 1256   # 제목, QR 미겹침 → 1304-48
    assert fields[1]["avail_w"] == 1256   # 일시, 미겹침


def test_template_carries_its_own_canvas():
    assert (TEMPLATES[0].canvas_w, TEMPLATES[0].canvas_h) == (1304, 984)


def test_field_avail_w_uses_the_given_canvas_not_a_global():
    """넘긴 캔버스 폭을 쓴다 — 전역이 새어 들어오면 미리보기가 거짓말을 한다."""
    tpl = TEMPLATES[0]
    f = tpl.fields[0]  # 제목 x=48, y=48, 80px — QR(968,648,288)과 안 겹침
    assert field_avail_w(f, tpl.qr, 1304) == 1256   # 1304 - 48
    assert field_avail_w(f, tpl.qr, 984) == 936     # 984 - 48


def test_as_dict_carries_canvas():
    data = as_dict()
    assert data[0]["canvas"] == {"w": 1304, "h": 984}


def test_portrait_template_is_984x1304():
    tpl = TEMPLATES[4]
    assert (tpl.canvas_w, tpl.canvas_h) == (984, 1304)
    assert tpl.name == "팀 소개"


def test_portrait_fonts_are_72_header_56_body():
    fs = [f.font_size for f in TEMPLATES[4].fields]
    assert fs == [72, 56, 56, 56]   # 팀명 72(큰), 주제 56(중간)


def test_font_sizes_are_the_three_baked():
    # 노드가 굽는 3크기(40/56/72)만 쓴다 (폰트 렌더 V2).
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert f.font_size in (40, 56, 72), f"{tpl.name}/{f.name} = {f.font_size}px"


def test_portrait_avail_w_is_the_narrow_canvas():
    tpl = TEMPLATES[4]
    for f in tpl.fields:
        assert field_avail_w(f, tpl.qr, tpl.canvas_w) == 936, f.name  # 984-48
