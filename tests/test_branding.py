from src.branding import channel_art as ca
from src.config import load_config


def test_banner_and_icon_sizes():
    vcfg = load_config()["video"]
    banner = ca.make_banner("テストチャンネル" * 3, "タグライン", ["A", "B"], vcfg["font"], vcfg["font_regular"])
    assert banner.size == ca.BANNER_SIZE
    assert ca.make_icon(vcfg["font"]).size == (ca.ICON_SIZE, ca.ICON_SIZE)


def test_main_writes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "OUT_DIR", tmp_path)
    assert [p.name for p in ca.main()] == ["banner.png", "icon.png"]
