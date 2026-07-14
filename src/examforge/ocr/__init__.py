"""OCR / 公式识别服务层。

第一版目标是把 Web 录入页和后续真实 OCR 服务解耦:
- mock: 本地演示/测试,不调用外部服务;
- tencent / aliyun: 通过配置的 HTTP endpoint 调用兼容代理或网关,并尽量解析常见返回结构。

说明: 腾讯云/阿里云官方接口通常需要云厂商签名。为了避免在 Web 进程里硬编码
各厂商 Action 与签名细节,生产环境推荐在 endpoint 后面接一个轻量代理/云函数,
由代理完成签名后返回 {latex/text/content} 等结构。本层负责统一文件上传、错误处理
和 LaTeX 文本抽取。
"""

from .service import OCRError, OCRResult, recognize_math_image

__all__ = ["OCRError", "OCRResult", "recognize_math_image"]
