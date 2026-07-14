from pathlib import Path

from fastapi.testclient import TestClient

from examforge.web import create_app
from examforge.repositories import reset_db_engine_for_tests, reset_vector_for_tests


def test_ingest_ocr_endpoint_mock(tmp_path: Path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    import examforge.config.settings as mod
    mod._store = None
    app = create_app(tmp_path / "data")
    c = TestClient(app)
    r = c.post(
        "/ingest/ocr",
        data={"provider": "mock"},
        files={"figure": ("formula.png", b"fake", "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["provider"] == "mock"
    assert "LaTeX" not in body["latex_text"]  # 返回的是可直接填入的题目文本
    assert "f(x)" in body["latex_text"]
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    mod._store = None



def test_ingest_page_textareas_support_paste_image_ocr(tmp_path: Path):
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    import examforge.config.settings as mod
    mod._store = None
    app = create_app(tmp_path / "data")
    c = TestClient(app)
    r = c.get("/ingest")
    assert r.status_code == 200
    html = r.text
    assert "直接 Ctrl+V 粘贴图片并 OCR 识别" in html
    assert html.count('data-paste-ocr="true"') >= 8
    assert html.count('data-paste-text-image="true"') == 4
    assert 'textarea name="stem"' in html
    assert 'textarea name="answer"' in html
    assert 'textarea name="official_analysis_steps"' in html
    assert 'textarea name="reference"' in html
    assert "题目文本、答案、官方解析、参考答案/补充解析均可直接 Ctrl+V 粘贴文字" in html
    assert "支持 Ctrl+V 粘贴文字" in html
    assert "参考答案/补充解析(可选)" in html
    assert "兼容旧字段:参考答案" not in html
    assert 'input name="region"' in html
    assert 'input name="source"' in html
    assert 'input name="sub_knowledge"' in html
    assert 'input name="problem_type_tags"' in html
    assert "attachPasteImageOcr" in html
    assert "firstImageFromPaste" in html
    assert "insertTextAtCursor" in html
    assert "Ctrl+V 直接粘贴截图作为题图上传" in html
    assert 'id="figure-paste-zone"' in html
    assert 'id="figure-preview"' in html
    assert 'id="figure-paste-status"' in html
    assert "attachFigurePasteUpload" in html
    assert "setFigureInputFile" in html
    assert "handleFigurePaste" in html
    assert "new DataTransfer" in html
    reset_db_engine_for_tests()
    reset_vector_for_tests()
    mod._store = None
