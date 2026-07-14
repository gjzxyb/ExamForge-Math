"""运行时配置存储 + 持久化。

启动时从环境变量加载(保持向后兼容),Web 配置页可运行时改写,
下次工厂调用即生效。持久化到 data/settings.json。
"""

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class LLMSettings:
    backend: str = "mock"          # mock | http
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    timeout: float = 60.0


@dataclass
class ModelControlSettings:
    """大模型全局约束与 Skill 指令。

    agent_md 类似项目级 AGENT.md / system policy，用于补充模型行为边界、
    输出风格和禁止事项；skills_md 用 Markdown 定义可被模型按需调用的
    “技能说明”，例如公式识别、专题报告、问答讲解等场景策略。
    """
    enabled: bool = False
    agent_md: str = ""
    skills_enabled: bool = False
    skills_md: str = ""


@dataclass
class EmbedderSettings:
    backend: str = "mock"          # mock | http
    base_url: str = "https://api.example.com"
    api_key: str = ""
    model: str = "text-embedding-3-small"
    dim: int = 1024
    timeout: float = 30.0


@dataclass
class WebSearchSettings:
    """全网搜索 API 配置,用于方法库发现外部优秀方法。"""
    provider: str = "mock"  # disabled | mock | serpapi | bing | custom
    endpoint: str = ""
    api_key: str = ""
    timeout: float = 20.0


@dataclass
class OCRSettings:
    """公式识别配置。

    provider 支持 none/mock/tencent/aliyun。tencent/aliyun 建议配置为自建代理
    endpoint,由代理负责云厂商签名,本应用负责上传图片和解析返回 LaTeX。
    """
    provider: str = "none"         # none | mock | tencent | aliyun
    access_key_id: str = ""
    access_key_secret: str = ""
    region: str = ""
    endpoint: str = ""


@dataclass
class Settings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    model_control: ModelControlSettings = field(default_factory=ModelControlSettings)
    embedder: EmbedderSettings = field(default_factory=EmbedderSettings)
    web_search: WebSearchSettings = field(default_factory=WebSearchSettings)
    ocr: OCRSettings = field(default_factory=OCRSettings)

    def to_dict(self) -> dict:
        return {
            "llm": asdict(self.llm),
            "model_control": asdict(self.model_control),
            "embedder": asdict(self.embedder),
            "web_search": asdict(self.web_search),
            "ocr": asdict(self.ocr),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        return cls(
            llm=LLMSettings(**data.get("llm", {})),
            model_control=ModelControlSettings(**data.get("model_control", {})),
            embedder=EmbedderSettings(**data.get("embedder", {})),
            web_search=WebSearchSettings(**data.get("web_search", {})),
            ocr=OCRSettings(**data.get("ocr", {})),
        )


class SettingsStore:
    """线程安全的单例,持久化到 settings.json。

    启动时:load_from_env() 把环境变量填进去(允许空 key),再 load_from_disk() 覆盖。
    Web 改写:update(...) → save()。
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "settings.json"
        self._lock = threading.RLock()
        self._settings = Settings()
        self._loaded = False

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._settings = _from_env(self._settings)
            self._settings = self._load_from_disk(self._settings)
            self._loaded = True

    def get(self) -> Settings:
        self.ensure_loaded()
        return self._settings

    def update(self, **kwargs) -> Settings:
        """支持 llm / model_control / embedder / web_search / ocr 五块整体替换。"""
        self.ensure_loaded()
        with self._lock:
            cur = self._settings
            if "llm" in kwargs:
                cur.llm = LLMSettings(**{**asdict(cur.llm), **kwargs["llm"]})
            if "model_control" in kwargs:
                cur.model_control = ModelControlSettings(**{
                    **asdict(cur.model_control), **kwargs["model_control"]})
            if "embedder" in kwargs:
                cur.embedder = EmbedderSettings(**{
                    **asdict(cur.embedder), **kwargs["embedder"]})
            if "web_search" in kwargs:
                cur.web_search = WebSearchSettings(**{
                    **asdict(cur.web_search), **kwargs["web_search"]})
            if "ocr" in kwargs:
                cur.ocr = OCRSettings(**{**asdict(cur.ocr), **kwargs["ocr"]})
            self._save_to_disk(cur)
            return cur

    def _load_from_disk(self, base: Settings) -> Settings:
        if not self.path.exists():
            return base
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return Settings.from_dict(data)
        except Exception:
            return base

    def _save_to_disk(self, s: Settings) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(s.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ---- 模块级单例 --------------------------------------------------------

_store: Optional[SettingsStore] = None


def init_settings_store(data_dir: Path) -> SettingsStore:
    global _store
    _store = SettingsStore(data_dir)
    _store.ensure_loaded()
    return _store


def get_settings_store() -> SettingsStore:
    if _store is None:
        raise RuntimeError("init_settings_store() 必须先调用")
    return _store


def get_settings() -> Settings:
    return get_settings_store().get()


def _from_env(s: Settings) -> Settings:
    """环境变量覆盖(仅当显式设置时)。允许 key 留空。"""
    def _set(name: str, target, attr: str) -> None:
        v = os.environ.get(name)
        if v is not None:
            setattr(target, attr, v)

    def _set_bool(name: str, target, attr: str) -> None:
        v = os.environ.get(name)
        if v is None:
            return
        setattr(target, attr, v.strip().lower() in {"1", "true", "yes", "on"})

    _set("EXAMFORGE_LLM_BACKEND", s.llm, "backend")
    _set("EXAMFORGE_LLM_BASE", s.llm, "base_url")
    _set("EXAMFORGE_LLM_KEY", s.llm, "api_key")
    _set("EXAMFORGE_LLM_MODEL", s.llm, "model")
    _set_bool("EXAMFORGE_MODEL_CONTROL_ENABLED", s.model_control, "enabled")
    _set("EXAMFORGE_MODEL_AGENT_MD", s.model_control, "agent_md")
    _set_bool("EXAMFORGE_MODEL_SKILLS_ENABLED", s.model_control, "skills_enabled")
    _set("EXAMFORGE_MODEL_SKILLS_MD", s.model_control, "skills_md")

    _set("EXAMFORGE_EMBED_BACKEND", s.embedder, "backend")
    _set("EXAMFORGE_EMBED_BASE", s.embedder, "base_url")
    _set("EXAMFORGE_EMBED_KEY", s.embedder, "api_key")
    _set("EXAMFORGE_EMBED_MODEL", s.embedder, "model")
    _set("EXAMFORGE_EMBED_DIM", s.embedder, "dim")

    _set("EXAMFORGE_SEARCH_PROVIDER", s.web_search, "provider")
    _set("EXAMFORGE_SEARCH_ENDPOINT", s.web_search, "endpoint")
    _set("EXAMFORGE_SEARCH_API_KEY", s.web_search, "api_key")

    _set("EXAMFORGE_OCR_PROVIDER", s.ocr, "provider")
    _set("EXAMFORGE_OCR_KEY_ID", s.ocr, "access_key_id")
    _set("EXAMFORGE_OCR_KEY_SECRET", s.ocr, "access_key_secret")
    _set("EXAMFORGE_OCR_REGION", s.ocr, "region")
    _set("EXAMFORGE_OCR_ENDPOINT", s.ocr, "endpoint")

    # 数值字段
    raw_dim = os.environ.get("EXAMFORGE_EMBED_DIM")
    if raw_dim:
        try:
            s.embedder.dim = int(raw_dim)
        except ValueError:
            pass
    raw_search_timeout = os.environ.get("EXAMFORGE_SEARCH_TIMEOUT")
    if raw_search_timeout:
        try:
            s.web_search.timeout = float(raw_search_timeout)
        except ValueError:
            pass
    return s