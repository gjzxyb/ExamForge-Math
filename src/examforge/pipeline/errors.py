"""管线自定义异常。"""


class PipelineError(Exception):
    """所有管线错误的基类。"""


class IngestValidationError(PipelineError):
    """录入数据校验失败。"""


class LLMSchemaError(PipelineError):
    """LLM 输出不符合 schema 多次重试后仍失败。"""


class NotInReviewQueue(PipelineError):
    """操作了不在审核队列的对象。"""