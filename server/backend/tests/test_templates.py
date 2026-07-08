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
