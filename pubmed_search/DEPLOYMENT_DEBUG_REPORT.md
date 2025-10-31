# PubMed Search 部署问题诊断报告

## 问题总结

当前部署在Render上的`pubmed_search`应用存在以下问题：
1. AI生成查询功能：后端正常工作，但前端无法显示生成的查询
2. 前后端数据链路：数据传输正常，但UI更新失败

## 详细诊断

### 1. 后端功能 ✅ 正常

**测试结果**：
- API端点：`/api/generate_query`
- 状态码：200 OK
- 响应数据：
```json
{
  "success": true,
  "query": "(\"端粒长度与衰老和长寿的关系研究\"[tiab])",
  "fallback_used": true,
  "topic": "端粒长度与衰老和长寿的关系研究"
}
```

### 2. 前端代码 ✅ 已更新

**代码版本**：最新版本（包含详细日志）
**JavaScript逻辑**：正确
```javascript
if (data.success) {
    queryInput.value = data.query;
    showToast('AI查询生成成功！', 'success');
}
```

### 3. 实际问题 ❌ 静态文件未加载

**问题现象**：
- 页面HTML中缺少CSS和JS文件的引用
- `<link>` 和 `<script>` 标签在渲染后消失

**预期HTML**（base.html模板）：
```html
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>搜索 - AI PubMed Search</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
</head>
```

**实际HTML**（浏览器接收）：
```html
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>搜索 - AI PubMed Search</title>
    
    
    
</head>
```

**静态文件验证**：
- ✅ CSS文件存在：`https://pubmed-search-4nr1.onrender.com/static/css/style.css`
- ✅ JS文件存在：`https://pubmed-search-4nr1.onrender.com/static/js/main.js`
- ❌ 但页面未引用这些文件

### 4. 根本原因

**可能的原因**：
1. Flask的`url_for`函数在生产环境中未正确工作
2. 静态文件路径配置问题
3. Render部署时静态文件未正确包含

**当前Render配置**：
```json
{
  "buildCommand": "pip install -r pubmed_search/requirements.txt",
  "startCommand": "gunicorn -w 2 -b 0.0.0.0:$PORT pubmed_search.app:app",
  "rootDir": ""
}
```

## 修复方案

### 方案1：检查Flask静态文件配置

在`pubmed_search/app.py`中添加静态文件配置：

```python
app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static')
```

### 方案2：使用绝对路径

修改`base.html`，使用绝对路径而不是`url_for`：

```html
<link href="/static/css/style.css" rel="stylesheet">
<script src="/static/js/main.js"></script>
```

### 方案3：检查Render部署配置

确保静态文件在部署时被正确包含：
1. 检查`.gitignore`，确保`static/`目录未被忽略
2. 确认`static/`目录在Git仓库中
3. 重新部署应用

### 方案4：添加静态文件路由

在`app.py`中添加显式的静态文件路由：

```python
from flask import send_from_directory

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)
```

## 推荐修复步骤

1. **立即修复**：使用方案2（绝对路径）
   - 修改`pubmed_search/templates/base.html`
   - 提交并推送到GitHub
   - 等待Render自动部署

2. **验证修复**：
   - 访问 https://pubmed-search-4nr1.onrender.com/search
   - 检查浏览器开发者工具的Network标签
   - 确认CSS和JS文件被正确加载

3. **测试功能**：
   - 输入研究主题
   - 点击"生成AI查询"
   - 验证查询框是否填充了生成的查询

## 测试数据

**测试主题**：端粒长度与衰老和长寿的关系研究

**预期结果**：
- 查询框填充：`("端粒长度与衰老和长寿的关系研究"[tiab])`
- Toast提示：AI查询生成成功！

## 附加信息

**部署URL**：https://pubmed-search-4nr1.onrender.com
**服务ID**：srv-d41s16m3jp1c739kcotg
**GitHub仓库**：https://github.com/zcJohnMc/pubmed-search
**分支**：main

**调试时间**：2025-10-31
**调试工具**：Chrome DevTools, Render API, MCP Chrome

