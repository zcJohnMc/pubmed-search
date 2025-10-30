from app import app

if __name__ == '__main__':
    print("🚀 启动AI PubMed搜索工具...")
    print("📱 访问地址: http://localhost:5000")
    print("🔧 开发模式: 已启用")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
