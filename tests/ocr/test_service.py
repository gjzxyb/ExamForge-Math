import json

import pytest

from examforge.ocr import OCRError, format_math_ocr_text, recognize_math_image
from examforge.config.settings import OCRSettings
from examforge.ocr import service
from examforge.ocr.service import (
    _aliyun_endpoint_host,
    _extract_aliyun_layout_text,
    _extract_text,
    _is_aliyun_official_endpoint,
)


def test_mock_ocr_returns_latex_text():
    out = recognize_math_image(b"image", filename="a.png", provider="mock")
    assert out.provider == "mock"
    assert "f(x)" in out.latex_text


def test_none_ocr_is_user_friendly_error():
    with pytest.raises(OCRError) as e:
        recognize_math_image(b"image", provider="none")
    assert "OCR 未启用" in str(e.value)


def test_aliyun_official_endpoint_detection():
    endpoint = "https://ocr-api.cn-hangzhou.aliyuncs.com"
    assert _is_aliyun_official_endpoint(endpoint)
    assert _is_aliyun_official_endpoint("ocr-api.aliyuncs.com")
    assert not _is_aliyun_official_endpoint("https://ocr.example.com/proxy")
    assert _aliyun_endpoint_host(endpoint) == "ocr-api.cn-hangzhou.aliyuncs.com"


def test_extract_text_decodes_aliyun_data_json_string():
    data = {"Data": '{"content": "函数 $f(x)=x^2$"}'}
    assert _extract_text(data) == "函数 $f(x)=x^2$"


def test_extract_aliyun_layout_text_restores_blocks_and_merges_visual_wrap():
    words = [
        {"word": "已知函数", "pos": [{"x": 0, "y": 10}]},
        {"word": "f(x).", "pos": [{"x": 60, "y": 11}]},
        {"word": "(1)证明：", "pos": [{"x": 0, "y": 35}]},
        {"word": "结论；", "pos": [{"x": 70, "y": 35}]},
        {"word": "①设函数", "pos": [{"x": 24, "y": 60}]},
        {"word": "单", "pos": [{"x": 430, "y": 60}]},
        {"word": "调递减；", "pos": [{"x": 0, "y": 80}]},
        {"word": "②比较大小.", "pos": [{"x": 24, "y": 105}]},
    ]
    data = {"Data": json.dumps({"content": "flat", "prism_wordsInfo": words})}

    assert _extract_aliyun_layout_text(data) == (
        "已知函数f(x).\n(1)证明：结论；\n①设函数单调递减；\n②比较大小."
    )


def test_extract_aliyun_layout_text_attaches_fraction_to_following_question():
    words = [
        {"word": "(1)若k=\\frac{1}{2}，求x_2，y_2；", "pos": [{"x": 0, "y": 10}]},
        {
            "word": "(3)设S_n为三角形面积。证明：S_n=S_{n+1}。",
            "pos": [{"x": 0, "y": 40}],
        },
        {"word": r"\frac{1+k}{1-k}", "pos": [{"x": 330, "y": 48}]},
        {
            "word": "(2)证明：数列{x_n-y_n}是公比为的等比数列；",
            "pos": [{"x": 0, "y": 60}],
        },
    ]
    data = {"Data": json.dumps({"prism_wordsInfo": words})}

    assert _extract_aliyun_layout_text(data) == (
        r"(1)若k=\frac{1}{2}，求x_2，y_2；"
        "\n"
        r"(2)证明：数列{x_n-y_n}是公比为\frac{1+k}{1-k}的等比数列；"
        "\n"
        "(3)设S_n为三角形面积。证明：S_n=S_{n+1}。"
    )

    formatted = format_math_ocr_text(_extract_aliyun_layout_text(data))
    assert r"公比为$\frac{1+k}{1-k}$的等比数列" in formatted
    assert r"等比数列；$\frac" not in formatted
    assert formatted.index("(1)") < formatted.index("(2)") < formatted.index("(3)")


def test_extract_aliyun_layout_text_defers_structured_array_to_vendor_content():
    words = [
        {"word": r"\left\{\begin{array}{l}-x^2-", "pos": [{"x": 150, "y": 10}]},
        {"word": r"\end{array}\right.", "pos": [{"x": 0, "y": 30}]},
        {"word": "2ax-a，x<0", "pos": [{"x": 0, "y": 50}]},
    ]
    data = {
        "content": r"已知函数f(x)=\left\{\begin{array}{l}-x^2-2ax-a，x<0，\\e^x+\ln(x+1)，x\ge0，\end{array}\right.在R上单调递增",
        "prism_wordsInfo": words,
    }

    assert _extract_aliyun_layout_text(data) == ""


def test_official_aliyun_endpoint_uses_signed_sdk_path(monkeypatch):
    settings = OCRSettings(
        provider="aliyun",
        access_key_id="ak",
        access_key_secret="sk",
        endpoint="https://ocr-api.cn-hangzhou.aliyuncs.com",
    )
    monkeypatch.setattr(service, "_settings_for", lambda provider: settings)
    called = {}

    def fake_official(image_bytes, **kwargs):
        called["image"] = image_bytes
        called.update(kwargs)
        return {"Data": '{"content": "识别结果 $x^2$"}'}

    monkeypatch.setattr(service, "_recognize_aliyun_official", fake_official)
    monkeypatch.setattr(
        service,
        "_recognize_proxy",
        lambda *args, **kwargs: pytest.fail("官方 Endpoint 不应走代理协议"),
    )

    result = recognize_math_image(b"image", provider="aliyun")

    assert result.latex_text == "识别结果$x^2$"
    assert result.raw_text == "识别结果 $x^2$"
    assert called["image"] == b"image"
    assert called["endpoint"] == settings.endpoint


def test_format_math_ocr_text_improves_exam_readability():
    raw = (
        "甲、乙两人进行乒乓球练习，每个球胜者得1分，负者得0分."
        "设每个球甲 胜的概率为 P \\left( \\frac { 1 } { 2 } < p < 1 \\right) ， ，"
        "乙胜的概率为 q，p+q=1， ，且各球的胜负相 互独立."
        "对正整数 k≥2， 记 p _ { k } 为打完k个球后甲比乙至少多得2分的概 率，"
        " qk 为打完k个球后乙比甲至少多得2分的概率. "
        "(1)求 p _ { 3 } ， p _ { 4 } (用p表示)；"
        "(2)若 \\frac { p _ { 4 } - p _ { 3 } } { q _ { 4 } - q _ { 3 } } = 4 ， ，求 "
        "(3)证明：对任意正整数 m，p2m+1-q2m+1<p2m-q2m<p2m+2-q2m+2"
    )

    formatted = format_math_ocr_text(raw)

    assert "甲胜的概率为$p$（$\\frac{1}{2}<p<1$）" in formatted
    assert "各球的胜负相互独立" in formatted
    assert "$p_k$" in formatted and "$q_k$" in formatted
    assert "\n(1) 求" in formatted
    assert "\n(2) 若" in formatted
    assert "\n(3) 证明" in formatted
    assert "$p_{2m+1}-q_{2m+1}<p_{2m}-q_{2m}<p_{2m+2}-q_{2m+2}$" in formatted
    assert "， ，" not in formatted
    assert "概 率" not in formatted


def test_format_math_ocr_text_preserves_left_command_and_normalizes_intervals():
    raw = (
        "已知函数 f \\left( x \\right) = \\ln \\left( 1 + x \\right) - k x ^ { 3 }，"
        "其中 0 < k < \\frac { 1 } { 3 } . "
        "(1)证明：f(x)在区间 (0，+∞) 上成立；"
        "① 证明：g(t)在区间 \\left( 0 ， x _ { 1 } \\right) 单 调递减；"
        "②比较 2 x _ { 1 } 与 x _ { 2 } 的大小。"
    )

    formatted = format_math_ocr_text(raw)

    assert "$f\\left(x\\right)=\\ln\\left(1+x\\right)-kx^3$" in formatted
    assert "$0<k<\\frac{1}{3}$。" in formatted
    assert "$\\left(0,+\\infty\\right)$" in formatted
    assert "$\\left(0,x_1\\right)$" in formatted
    assert "\\le ft" not in formatted
    assert "\n① 证明" in formatted
    assert "\n② 比较" in formatted


def test_format_math_ocr_text_uses_colon_before_numbered_subquestions():
    formatted = format_math_ocr_text("(2)设$x_1$为零点. ①证明结论； ②比较大小.")

    assert "零点：\n① 证明结论；\n② 比较大小。" in formatted


def test_format_math_ocr_text_removes_common_duplicate_ocr_tokens():
    raw = "(1)证明：：f(x) )在区间内；①设g(t). .证明结论；② ②比较大小。"

    formatted = format_math_ocr_text(raw)

    assert "$f(x)$在区间内" in formatted
    assert "$g(t)$。证明结论" in formatted
    assert formatted.count("②") == 1
    assert "：：" not in formatted
    assert "))" not in formatted
    assert ". ." not in formatted


def test_format_math_ocr_text_repairs_geometry_commands_and_symbols():
    raw = (
        "如图，在四边形ABCD中，AB\\parallelCD，\\angleDAB=90°，"
        "EFⅡAD，A'B∥CD'F，GH⊥AD，A'BⅡ平面CD'F。"
    )

    formatted = format_math_ocr_text(raw)

    assert "$ABCD$" in formatted
    assert "$AB\\parallel CD$" in formatted
    assert "$\\angle DAB=90^\\circ$" in formatted
    assert "$EF\\parallel AD$" in formatted
    assert "$A'B\\parallel CD'F$" in formatted
    assert "$GH\\perp AD$" in formatted
    assert "$A'B\\parallel$平面$CD'F$" in formatted
    assert "\\parallelCD" not in formatted
    assert "\\angleDAB" not in formatted
    assert "Ⅱ" not in formatted
    assert "∥" not in formatted
    assert "⊥" not in formatted


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r"由题意，\left(x_2>0\right。故结论成立。", r"$\left(x_2>0\right)$。"),
        (r"由题意，x_2>0\right。故结论成立。", r"$x_2>0$。"),
        (r"由题意，\left(x_2>0\right）故结论成立。", r"$\left(x_2>0\right)$"),
        (r"由题意，\left(x_2>0。故结论成立。", r"$\left(x_2>0\right)$。"),
    ],
)
def test_format_math_ocr_text_repairs_invalid_left_right_delimiters(raw, expected):
    formatted = format_math_ocr_text(raw)

    assert expected in formatted
    assert r"\right。" not in formatted
    assert r"\right）" not in formatted


def test_format_math_ocr_text_degrades_unpaired_scalable_commands():
    left_only = format_math_ocr_text(r"分别考察 \left[x>0 的情况。")
    right_only = format_math_ocr_text(r"由 x_2>0\right) 得到结论。")

    assert r"\left" not in left_only
    assert r"\right" not in right_only
    assert "Missing or unrecognized delimiter" not in left_only + right_only


@pytest.mark.parametrize(
    "raw",
    [
        r"${x_2>0\right。",
        r"$x_2>0\right。",
    ],
)
def test_format_math_ocr_text_closes_vendor_inline_math(raw):
    formatted = format_math_ocr_text(raw)

    assert formatted == r"$x_2>0$。"
    assert formatted.count("$") == 2


def test_format_math_ocr_text_repairs_malformed_set_delimiters():
    formatted = format_math_ocr_text(r"数列\left$\${x_n-y_n\right$\}是等比数列。")

    assert r"$\left\{x_n-y_n\right\}$" in formatted
    assert r"\left$" not in formatted
    assert r"\right$" not in formatted


def test_format_math_ocr_text_repairs_point_subscripts_and_triangle_vertices():
    formatted = format_math_ocr_text(
        r"过点P_n作斜率为k的直线与C的左支点交于点Qn-1，令Pn+1为Q_{n-1}关于y轴的对称点。"
        r"S_n为\triangle{P_n}{P_n+1}P_{n+2}的面积。"
    )

    assert "$P_n$" in formatted
    assert "$Q_{n-1}$" in formatted
    assert "$P_{n+1}$" in formatted
    assert r"$\triangle P_nP_{n+1}P_{n+2}$" in formatted


def test_format_math_ocr_text_removes_extra_inline_dollar_without_touching_block_math():
    assert format_math_ocr_text(r"S_n=S_{n+1}$$。") == r"$S_n=S_{n+1}$。"
    assert format_math_ocr_text(r"$$x^2$$。") == r"$$x^2$$。"


def test_format_math_ocr_text_restores_polar_equation_and_parametric_line_order():
    raw = (
        "22。在直角坐标系x Oy中，以坐标原点为极点，$x$轴正半轴为极轴建立极坐标系，"
        "曲线$C$的极坐标方程为ρ$=$ρcosθ$+1$。\n"
        "(1) 写出$C$的直角坐标方程；\n"
        r"$l$：$\left\{\begin{array}{l}x=t$，\\ $y=t+a \end{array}\right$。"
        "\n(2) 设直线（$t$为参数），若$C$与$l$相交于$A$，$B$两点，"
        "且|$AB$|$=2$，求$a$。"
    )

    formatted = format_math_ocr_text(raw)

    assert "$xOy$" in formatted
    assert r"$\rho=\rho\cos\theta+1$" in formatted
    assert (
        r"(2) 设直线$l:\begin{cases}x=t,\\y=t+a\end{cases}$"
        r"（$t$为参数）"
    ) in formatted
    assert r"$|AB|=2$" in formatted
    assert formatted.index("(1)") < formatted.index("(2)")
    assert formatted.index("(2)") < formatted.index(r"\begin{cases}")
    assert r"\begin{array}" not in formatted
    assert "Missing" not in formatted


def test_format_math_ocr_text_repairs_piecewise_function_array():
    raw = (
        r"已知函数$f(x)=\left\{\begin{array}{l}-x^2-2ax-a$，$x<0$，\\ "
        r"$e^x+\ln(x+1)$，$x\ge0$，\end{array}\right.$在$R$上单调递增，"
        "则$a$的取值范围是（ ）"
    )

    formatted = format_math_ocr_text(raw)

    assert (
        r"$f(x)=\begin{cases}-x^2-2ax-a,&x<0,\\"
        r"e^x+\ln(x+1),&x\ge0,\end{cases}$"
    ) in formatted
    assert r"\begin{array}" not in formatted
    assert r"\end{array}" not in formatted
    assert formatted.count("$") % 2 == 0
