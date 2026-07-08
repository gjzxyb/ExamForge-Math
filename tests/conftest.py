import pytest
from pathlib import Path


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """每个测试一个临时数据目录(SQLite 与 Chroma 都用它)。"""
    d = tmp_path / "data"
    d.mkdir()
    return d
