from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import os
import json
from datetime import datetime
import uuid
import threading
import time
try:
    from .pubmed_search_core import (
        init_database, generate_pubmed_query_with_ai, generate_inclusive_fallback_query,
        search_pubmed, fetch_article_details, assign_scores_by_if, filter_articles,
        filter_articles_by_type, save_search_to_database, get_search_history,
        get_search_by_id, fetch_article_details_with_progress
    )
except ImportError:
    from pubmed_search_core import (
        init_database, generate_pubmed_query_with_ai, generate_inclusive_fallback_query,
        search_pubmed, fetch_article_details, assign_scores_by_if, filter_articles,
        filter_articles_by_type, save_search_to_database, get_search_history,
        get_search_by_id,
        fetch_article_details_with_progress
    )

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# 初始化数据库
init_database()

# 添加进度存储
search_progress = {}

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/search')
def search_page():
    """搜索页面"""
    return render_template('search.html')

@app.route('/history')
def history_page():
    """历史记录页面"""
    history = get_search_history(limit=20)
    return render_template('history.html', history=history)

@app.route('/history/<int:search_id>')
def view_history(search_id):
    """查看历史搜索结果"""
    search_data = get_search_by_id(search_id)
    
    if not search_data:
        return redirect(url_for('history_page'))
    
    articles = search_data['articles']
    search_info = search_data['search_info']
    
    # 构建搜索参数字典
    search_params = {
        'user_topic': search_info[2],
        'final_query': search_info[4],
        'journal_filter': search_info[5],
        'year_range': search_info[6]
    }
    
    # 分页参数
    page = int(request.args.get('page', 1))
    per_page = 20
    total_pages = (len(articles) + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_articles = articles[start_idx:end_idx]
    
    return render_template('history_results.html',
                         articles=page_articles,
                         search_params=search_params,
                         current_page=page,
                         total_pages=total_pages,
                         total_articles=len(articles),
                         search_id=search_id,
                         is_history=True)

@app.route('/api/generate_query', methods=['POST'])
def api_generate_query():
    """AI生成查询API - 带fallback机制"""
    try:
        data = request.get_json()
        user_topic = data.get('topic', '').strip()

        if not user_topic:
            return jsonify({'success': False, 'error': '请提供研究主题'})

        # 尝试使用AI生成查询
        ai_query = generate_pubmed_query_with_ai(user_topic)

        if ai_query:
            return jsonify({
                'success': True,
                'query': ai_query,
                'topic': user_topic,
                'fallback_used': False
            })
        else:
            # AI失败时使用fallback机制
            print(f"⚠️ AI生成失败，使用fallback查询: {user_topic}")
            fallback_query = generate_inclusive_fallback_query(user_topic)
            return jsonify({
                'success': True,
                'query': fallback_query,
                'topic': user_topic,
                'fallback_used': True
            })

    except Exception as e:
        print(f"❌ API错误: {e}")
        # 即使发生异常，也尝试返回fallback查询
        try:
            user_topic = request.get_json().get('topic', '').strip()
            if user_topic:
                fallback_query = generate_inclusive_fallback_query(user_topic)
                return jsonify({
                    'success': True,
                    'query': fallback_query,
                    'topic': user_topic,
                    'fallback_used': True,
                    'error_message': str(e)
                })
        except:
            pass
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/search', methods=['POST'])
def api_search():
    """执行搜索API - 支持进度推送"""
    try:
        data = request.get_json()
        
        # 获取搜索参数
        query = data.get('query', '').strip()
        user_topic = data.get('user_topic', '').strip()
        ai_generated_query = data.get('ai_generated_query', '').strip()
        journal_filter = data.get('journal_filter', '').strip()
        min_year = data.get('min_year', '').strip()
        max_year = data.get('max_year', '').strip()
        min_score = float(data.get('min_score', 0))
        article_types = data.get('article_types', ['all'])
        
        if not query:
            return jsonify({'success': False, 'error': '请提供搜索查询'})
        
        # 生成搜索会话ID
        search_session_id = str(uuid.uuid4())
        session['current_search'] = search_session_id
        
        # 初始化进度
        search_progress[search_session_id] = {
            'status': 'starting',
            'progress': 0,
            'message': '正在初始化搜索...',
            'total_articles': 0,
            'processed_articles': 0
        }
        
        # 在后台线程中执行搜索
        search_thread = threading.Thread(
            target=execute_search_with_progress,
            args=(search_session_id, query, user_topic, ai_generated_query,
                  journal_filter, min_year, max_year, min_score, article_types)
        )
        search_thread.daemon = True
        search_thread.start()
        
        return jsonify({
            'success': True,
            'search_session_id': search_session_id,
            'message': '搜索已开始，请等待...'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def execute_search_with_progress(search_session_id, query, user_topic, ai_generated_query,
                                journal_filter, min_year, max_year, min_score, article_types):
    """在后台执行搜索并更新进度"""
    with app.app_context():
        try:
            app.logger.info(f"Thread {search_session_id}: Starting search execution.")
            
            # 更新进度：开始搜索
            search_progress[search_session_id].update({
                'status': 'searching',
                'progress': 10,
                'message': '正在搜索PubMed数据库...'
            })
            app.logger.info(f"Thread {search_session_id}: Updated progress to 'searching'.")
            
            # 执行搜索
            search_result = search_pubmed( # Call to pubmed_search_core
                query=query,
                journal=journal_filter,
                min_year=min_year if min_year else None,
                max_year=max_year if max_year else None,
                main_journals_only=True
            )
            app.logger.info(f"Thread {search_session_id}: search_pubmed returned. PMIDs found: {len(search_result.get('pmids', [])) if search_result else 'None'}")

            if not search_result or (not search_result.get("pmids") and not (search_result.get("web_env") and search_result.get("query_key"))):
                search_progress[search_session_id].update({
                    'status': 'error',
                    'progress': 0,
                    'message': '未找到任何文章，请尝试其他搜索条件'
                })
                app.logger.warning(f"Thread {search_session_id}: No articles found by search_pubmed.")
                return
            
            total_found = search_result.get("total_count", 0)
            search_progress[search_session_id].update({
                'status': 'fetching',
                'progress': 30,
                'message': f'找到 {total_found} 篇文章，正在获取详细信息...',
                'total_articles': total_found
            })
            app.logger.info(f"Thread {search_session_id}: Updated progress to 'fetching'. Total found: {total_found}")
            
            # 获取文章详情（带进度回调）
            articles = fetch_article_details_with_progress( # Call to pubmed_search_core
                pmids=search_result.get("pmids"),
                web_env=search_result.get("web_env"),
                query_key=search_result.get("query_key"),
                main_journals_only=True,
                progress_callback=lambda processed, total: update_fetch_progress(
                    search_session_id, processed, total
                )
            )
            app.logger.info(f"Thread {search_session_id}: fetch_article_details_with_progress returned. Articles fetched: {len(articles) if articles else 'None'}")
            
            if not articles:
                search_progress[search_session_id].update({
                    'status': 'error',
                    'progress': 0,
                    'message': '未能获取到任何符合条件的文章详细信息'
                })
                app.logger.warning(f"Thread {search_session_id}: No article details fetched.")
                return
            
            # 更新进度：评分和过滤
            search_progress[search_session_id].update({
                'status': 'processing',
                'progress': 80,
                'message': '正在评分和过滤文章...'
            })
            app.logger.info(f"Thread {search_session_id}: Updated progress to 'processing'.")
            
            # 评分和过滤
            scored_articles = assign_scores_by_if(articles) # pubmed_search_core
            app.logger.info(f"Thread {search_session_id}: assign_scores_by_if returned. Scored articles: {len(scored_articles)}")
            filtered_articles = filter_articles(scored_articles, min_score) # pubmed_search_core
            app.logger.info(f"Thread {search_session_id}: filter_articles returned. Filtered articles: {len(filtered_articles)}")

            # 按文章类型筛选
            type_filtered_articles = filter_articles_by_type(filtered_articles, article_types) # pubmed_search_core
            app.logger.info(f"Thread {search_session_id}: filter_articles_by_type returned. Type filtered articles: {len(type_filtered_articles)}")
            
            # 准备搜索参数
            year_range_str = ""
            if min_year and max_year:
                year_range_str = f"{min_year}-{max_year}"
            elif min_year:
                year_range_str = f"{min_year}以后"
            elif max_year:
                year_range_str = f"{max_year}以前"
            
            # 准备文章类型显示字符串
            article_types_str = ""
            if 'all' in article_types:
                article_types_str = "所有类型"
            else:
                specific_types = [t for t in article_types if t != 'all']
                if specific_types:
                    article_types_str = ', '.join(specific_types)
                else:
                    article_types_str = "所有类型"

            search_params = {
                'user_topic': user_topic,
                'ai_generated_query': ai_generated_query,
                'final_query': query,
                'journal_filter': journal_filter if journal_filter else "所有预定义主刊",
                'year_range': year_range_str,
                'min_score': min_score,
                'article_types': article_types_str,
                'total_results': total_found
            }
            
            # 保存到数据库
            search_id = save_search_to_database(search_params, type_filtered_articles) # pubmed_search_core
            app.logger.info(f"Thread {search_session_id}: save_search_to_database returned. Search ID: {search_id}")

            # 准备结果数据，但不直接写入session
            results_data_payload = {
                'articles': type_filtered_articles,
                'search_params': search_params,
                'search_id': search_id
            }
            
            # 完成 - 将结果数据也放入search_progress
            search_progress[search_session_id].update({
                'status': 'completed',
                'progress': 100,
                'message': f'搜索完成！找到 {len(filtered_articles)} 篇符合条件的文章',
                'total_found': total_found,
                'filtered_count': len(filtered_articles),
                'search_id': search_id,
                'results_data': results_data_payload
            })
            app.logger.info(f"Thread {search_session_id}: Updated progress to 'completed'.")
            
        except Exception as e:
            app.logger.error(f"Thread {search_session_id}: Exception caught in execute_search_with_progress: {str(e)}", exc_info=True)
            search_progress[search_session_id].update({
                'status': 'error',
                'progress': 0,
                'message': f'搜索过程中发生错误: {str(e)}' # This message will be shown to the user
            })

def update_fetch_progress(search_session_id, processed, total):
    """更新获取文章的进度"""
    if search_session_id in search_progress:
        progress = 30 + int((processed / total) * 40)  # 30-70%
        search_progress[search_session_id].update({
            'progress': progress,
            'message': f'正在获取文章详情... ({processed}/{total})',
            'processed_articles': processed
        })

@app.route('/api/search_progress/<search_session_id>')
def api_search_progress(search_session_id):
    """获取搜索进度API"""
    if search_session_id in search_progress:
        current_progress_data = search_progress[search_session_id]
        
        # 如果搜索完成且结果尚未移至session，则处理结果数据
        if current_progress_data.get('status') == 'completed' and \
           f'search_results_{search_session_id}' not in session and \
           'results_data' in current_progress_data:
            
            session[f'search_results_{search_session_id}'] = current_progress_data['results_data']
            # 从search_progress中移除已处理的results_data以节省内存，
            # 注意：如果其他地方可能还需要它，或者前端可能基于此进行多次操作，则不应删除或应复制。
            # 为简单起见，这里我们选择不立即删除，以防万一。
            # 如果内存占用成为问题，可以考虑更复杂的清理策略。
            # 例如: del current_progress_data['results_data']

        return jsonify({
            'success': True,
            'progress': current_progress_data
        })
    else:
        return jsonify({
            'success': False,
            'error': '搜索会话不存在'
        })

@app.route('/search_progress/<search_session_id>')
def search_progress_page(search_session_id):
    """搜索进度页面"""
    return render_template('search_progress.html', search_session_id=search_session_id)

@app.route('/results/<search_session_id>')
def results_page(search_session_id):
    """结果页面"""
    search_data = session.get(f'search_results_{search_session_id}')
    
    if not search_data:
        return redirect(url_for('search_page'))
    
    articles = search_data['articles']
    search_params = search_data['search_params']
    
    # 分页参数
    page = int(request.args.get('page', 1))
    per_page = 20
    total_pages = (len(articles) + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_articles = articles[start_idx:end_idx]
    
    return render_template('results.html',
                         articles=page_articles,
                         search_params=search_params,
                         current_page=page,
                         total_pages=total_pages,
                         total_articles=len(articles),
                         search_session_id=search_session_id)

@app.route('/api/export/<search_session_id>/<format>')
def api_export(search_session_id, format):
    """导出结果API"""
    try:
        search_data = session.get(f'search_results_{search_session_id}')
        
        if not search_data:
            return jsonify({'success': False, 'error': '搜索结果不存在'})
        
        articles = search_data['articles']
        search_params = search_data['search_params']
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == 'json':
            filename = f"pubmed_search_{timestamp}.json"
            export_data = {
                "search_parameters": search_params,
                "articles": articles
            }
            
            return jsonify({
                'success': True,
                'filename': filename,
                'data': export_data
            })
        
        elif format == 'markdown':
            md_content = generate_markdown_content(articles, search_params)
            
            return jsonify({
                'success': True,
                'filename': f"pubmed_search_{timestamp}.md",
                'content': md_content
            })
        
        else:
            return jsonify({'success': False, 'error': '不支持的导出格式'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/export_history/<int:search_id>/<format>')
def api_export_history(search_id, format):
    """导出历史搜索结果API"""
    try:
        search_data = get_search_by_id(search_id)
        
        if not search_data:
            return jsonify({'success': False, 'error': '搜索结果不存在'})
        
        articles = search_data['articles']
        search_info = search_data['search_info']
        
        search_params = {
            'user_topic': search_info[2],
            'final_query': search_info[4],
            'journal_filter': search_info[5],
            'year_range': search_info[6]
        }
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == 'json':
            filename = f"pubmed_history_{search_id}_{timestamp}.json"
            export_data = {
                "search_parameters": search_params,
                "articles": articles
            }
            
            return jsonify({
                'success': True,
                'filename': filename,
                'data': export_data
            })
        
        elif format == 'markdown':
            md_content = generate_markdown_content(articles, search_params)
            
            return jsonify({
                'success': True,
                'filename': f"pubmed_history_{search_id}_{timestamp}.md",
                'content': md_content
            })
        
        else:
            return jsonify({'success': False, 'error': '不支持的导出格式'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def generate_markdown_content(articles, search_params):
    """生成Markdown内容"""
    content = f"""# PubMed搜索结果

**搜索关键词**: `{search_params.get('final_query', '')}`  
**期刊过滤**: {search_params.get('journal_filter', '')}  
**年份范围**: {search_params.get('year_range', '')}  
**搜索日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**结果数量**: {len(articles)}篇文章  

## 目录

"""
    
    for i, article in enumerate(articles, 1):
        content += f"{i}. [{article['title']}](#article-{i})  \n"
    
    content += "\n---\n\n## 文章详情\n\n"
    
    for i, article in enumerate(articles, 1):
        content += f"""### {i}. {article['title']} {{#article-{i}}}

| 项目 | 内容 |
| --- | --- |
| 期刊 | {article['journal']} |
| 影响因子 | {article.get('impact_factor', 'N/A')} |
| 年份 | {article['year']} |
| 评分 | {article.get('score', 'N/A')} |

**作者**: {', '.join(article['authors'])}

**摘要**:  
{article['abstract']}

**链接**:  
- PubMed: [{article['pmid']}]({article['pubmed_url']})  
"""
        if article.get('doi'):
            content += f"- DOI: [{article['doi']}](https://doi.org/{article['doi']})  \n"
        
        content += "\n---\n\n"
    
    return content

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
