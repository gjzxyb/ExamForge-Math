"""冒烟测试:确认包导入与版本可读。"""


def test_package_imports():
    import examforge
    assert examforge.__version__ == "0.1.0"


def test_conftest_fixture_isolates(tmp_path):
    # 验证 tmp_path/conftest fixture 可用
    assert tmp_path.exists()
