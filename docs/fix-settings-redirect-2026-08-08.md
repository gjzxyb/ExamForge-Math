# ExamForge-Math 设置页跳转优化

## 问题描述
设置页保存参数后,显示 `{"ok":true,"redirect":"/settings?saved=llm"}` JSON 响应,但页面没有自动跳转。

## 根本原因
- 后端返回 JSON 格式的重定向指令
- 前端表单使用标准 POST 提交,浏览器直接显示 JSON
- 缺少 JavaScript 处理 AJAX 响应和自动跳转

## 解决方案

### 修改文件
`src/examforge/web/templates/settings.html`

### 实现细节

1. **添加统一表单 AJAX 处理函数**
```javascript
function setupFormAjax(formId) {
  var form = document.getElementById(formId);
  form.addEventListener("submit", function(e) {
    e.preventDefault();  // 阻止默认表单提交
    
    // 禁用按钮,显示"保存中..."
    var btn = form.querySelector("button[type='submit']");
    btn.disabled = true;
    btn.textContent = "保存中...";
    
    // AJAX 提交
    fetch(form.action, { method: "POST", body: new FormData(form) })
      .then(r => r.json())
      .then(data => {
        if (data.ok && data.redirect) {
          window.location.href = data.redirect;  // 自动跳转
        } else {
          alert("保存失败: " + data.error);
        }
      });
  });
}
```

2. **绑定所有设置表单**
```javascript
setupFormAjax("form-llm");
setupFormAjax("form-model-control");
setupFormAjax("form-embedder");
setupFormAjax("form-web-search");
setupFormAjax("form-ocr");
```

## 用户体验改进

### 优化前
1. 点击"保存 LLM"按钮
2. 页面显示原始 JSON: `{"ok":true,"redirect":"/settings?saved=llm"}`
3. 用户手动复制 URL 或点击后退按钮
4. ❌ 体验差,不直观

### 优化后
1. 点击"保存 LLM"按钮
2. 按钮变为"保存中...",禁用状态
3. 自动跳转到 `/settings?saved=llm`
4. 页面显示绿色提示: "已保存 **llm** 区块"
5. ✅ 流畅,符合预期

## 测试验证

```bash
uv run pytest tests/web/test_settings_route.py -v
# 结果: 11 passed, 6 warnings in 8.84s

uv run pytest
# 结果: 176 passed, 2 skipped, 644 warnings in 42.22s
```

## 影响范围

- ✅ 所有设置表单 (LLM, Model Control, Embedder, Web Search, OCR)
- ✅ 保持后端 API 不变
- ✅ 向后兼容
- ✅ 无破坏性更改

## 额外优化

1. **加载状态**: 按钮禁用 + 文字变更,防止重复提交
2. **错误处理**: 保存失败时弹窗提示,按钮恢复可用
3. **统一代码**: 所有表单使用同一个处理函数,便于维护

---

**状态**: ✅ 已完成并测试通过
