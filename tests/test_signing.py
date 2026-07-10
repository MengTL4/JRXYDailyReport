from sandau_checkin.signing import make_signature


def test_signature_matches_fixed_vector():
    signature = make_signature("TEST2026001", timestamp_ms=1700000000123)

    assert signature.ts == "1700000000123"
    assert signature.decodes == "5C2A01D4F0F744B7080E3720DE93B986"


def test_generated_timestamp_is_milliseconds():
    signature = make_signature("TEST2026001")

    assert signature.ts.isdigit()
    assert len(signature.ts) == 13
    assert len(signature.decodes) == 32
    assert signature.decodes == signature.decodes.upper()
