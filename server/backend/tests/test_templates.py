from app.protocol.templates import (
    BLACK, PAPER, RED, TEMPLATES, FieldDef, QrDef,
    as_dict, field_avail_w, field_max_bytes,
)


def test_four_confirmed_templates():
    # 확정 4: 0 행사안내 · 1 일정표 · 2 프로젝트소개(가로) · 3 프로젝트소개(세로)
    assert set(TEMPLATES) == {0, 1, 2, 3}


def test_field_ids_sequential():
    for tpl in TEMPLATES.values():
        assert [f.id for f in tpl.fields] == list(range(len(tpl.fields))), tpl.name


def test_font_sizes_are_the_three_baked():
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert f.font_size in (40, 56, 72), f"{tpl.name}/{f.name} = {f.font_size}"
        for lb in tpl.labels:
            assert lb.font_size in (40, 56, 72), f"{tpl.name}/{lb.text}"


def test_text_colors_valid():
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert f.color in (BLACK, RED, PAPER), f"{tpl.name}/{f.name}"
        for lb in tpl.labels:
            assert lb.color in (BLACK, RED, PAPER), f"{tpl.name}/{lb.text}"


def test_deco_colors_valid():
    for tpl in TEMPLATES.values():
        for d in tpl.decorations:
            assert d.fill in ("none", BLACK, RED) and d.stroke in ("none", BLACK, RED)


def test_max_bytes_in_range():
    # 분할 SET_FIELD 로 필드 상한은 FIELD_MAX_TEXT(512). 단일 패킷 필드(h=0)는 여전히 ≤198.
    from app.protocol.packet import FIELD_MAX_TEXT
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            mb = field_max_bytes(f, tpl.qr, tpl.canvas_w)
            assert 0 < mb <= FIELD_MAX_TEXT, f"{tpl.name}/{f.name} = {mb}"
            if not f.h:
                assert mb <= 198, f"단일 필드 {tpl.name}/{f.name} = {mb} > 198"


def test_geometry_inside_canvas():
    for tpl in TEMPLATES.values():
        w, h = tpl.canvas_w, tpl.canvas_h
        for f in tpl.fields:
            assert 0 <= f.x < w and 0 <= f.y < h, f"{tpl.name}/{f.name}"
        assert tpl.qr.x + tpl.qr.size <= w and tpl.qr.y + tpl.qr.size <= h, tpl.name
        for d in tpl.decorations:
            assert d.x >= 0 and d.y >= 0 and d.x + d.w <= w and d.y + d.h <= h, f"{tpl.name} deco"
        for lb in tpl.labels:
            assert 0 <= lb.x < w and 0 <= lb.y < h, f"{tpl.name}/{lb.text}"


def test_field_w_override_wins():
    f = FieldDef(0, "x", 100, 100, 56, w=270)
    assert field_avail_w(f, QrDef(0, 0, 0), 1304) == 270   # QR 무관, 명시 폭


def test_field_avail_shrinks_only_for_qr_overlap():
    qr = QrDef(900, 300, 200)                 # x900, y 300~500
    over = FieldDef(0, "o", 48, 320, 56)      # y 320~376 겹침 → QR 앞까지
    clear = FieldDef(1, "c", 48, 100, 56)     # y 100~156 안 겹침 → 캔버스 끝
    assert field_avail_w(over, qr, 1304) == 900 - 48
    assert field_avail_w(clear, qr, 1304) == 1304 - 48


def test_portrait_template_is_984x1304():
    assert (TEMPLATES[3].canvas_w, TEMPLATES[3].canvas_h) == (984, 1304)


def test_landscape_templates_are_1304x984():
    for tid in (0, 1, 2):
        assert (TEMPLATES[tid].canvas_w, TEMPLATES[tid].canvas_h) == (1304, 984)


def test_as_dict_carries_new_shape():
    d = as_dict()
    assert len(d) == 4
    t0 = d[0]
    f0 = t0["fields"][0]
    assert f0["name"] and f0["color"] in (BLACK, RED, PAPER)
    assert "avail_w" in f0 and "max_bytes" in f0
    assert t0["decorations"] and {"x", "y", "w", "h", "fill", "stroke"} <= set(t0["decorations"][0])
    assert t0["labels"] and t0["labels"][0]["text"]
    assert t0["canvas"] == {"w": 1304, "h": 984}
    assert {"x", "y", "size"} <= set(t0["qr"].keys())
