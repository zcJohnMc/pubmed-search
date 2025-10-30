# pubmed_search_core.py
# 核心PubMed搜索功能模块

import requests
import xml.etree.ElementTree as ET
import time
import re
import os
import json
import sqlite3
from datetime import datetime

# 设置API密钥和基础URL (PubMed E-utilities)
PUBMED_API_KEY = os.environ.get("PUBMED_API_KEY", "b6a22ac9a183cabddf8a38046641c2378308")
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# OpenRouter API Configuration
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "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")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
YOUR_SITE_URL = "http://localhost:5000"
YOUR_SITE_NAME = "AI PubMed Query Tool"

# 数据库配置
import os
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "pubmed_search_history.db"))

# 定义主刊和子刊列表 (32个期刊)
MAIN_JOURNALS = {
    "Nature Reviews Genetics": ["Nature Reviews Genetics"],
    "Nature Structural & Molecular Biology": ["Nature Structural & Molecular Biology", "Nature Structural and Molecular Biology"],
    "Molecular Cell": ["Molecular Cell"],
    "Genome Biology": ["Genome Biology"],
    "Epigenetics & Chromatin": ["Epigenetics & Chromatin", "Epigenetics and Chromatin"],
    "Clinical Epigenetics": ["Clinical Epigenetics"],
    "Epigenetics": ["Epigenetics"],
    "Nature": ["Nature"],
    "Science": ["Science"],
    "Cell": ["Cell"],
    "Nature Genetics": ["Nature Genetics"],
    "Cell Reports": ["Cell Reports"],
    "Nature Communications": ["Nature Communications"],
    "Science Advances": ["Science Advances"],
    "Cancer Discovery": ["Cancer Discovery"],
    "Cell Metabolism": ["Cell Metabolism"],
    "Journal of Clinical Investigation": ["Journal of Clinical Investigation", "JCI"],
    "Oncogene": ["Oncogene"],
    "Cancer Research": ["Cancer Research"],
    "Clinical Cancer Research": ["Clinical Cancer Research"],
    "Nature Reviews Cancer": ["Nature Reviews Cancer"],
    "Bioinformatics": ["Bioinformatics"],
    "PLOS Computational Biology": ["PLOS Computational Biology", "PLoS Computational Biology"],
    "Briefings in Bioinformatics": ["Briefings in Bioinformatics"],
    "Nucleic Acids Research": ["Nucleic Acids Research"],
    "Nature Machine Intelligence": ["Nature Machine Intelligence"],
    "Cell Systems": ["Cell Systems"],
    "IEEE/ACM Trans. Comp. Bio. & Bioinf.": ["IEEE/ACM Trans. Comp. Bio. & Bioinf.", "IEEE/ACM Transactions on Computational Biology and Bioinformatics"],
    "Journal of Biomedical Informatics": ["Journal of Biomedical Informatics"],
    "Artificial Intelligence in Medicine": ["Artificial Intelligence in Medicine"],
    "Patterns": ["Patterns"],
    "Database (Biol. Databases & Curation)": ["Database (Biol. Databases & Curation)", "Database"],
    "GigaScience": ["GigaScience"]
}

SUBSIDIARY_PATTERNS = [
    r"Nature\s+[A-Z]", r"Cell\s+[A-Z]", r"Science\s+[A-Z]",
    r"Lancet\s+[A-Z]", r"JAMA\s+[A-Z]", r"BMJ\s+[A-Z]"
]

JOURNAL_IMPACT_FACTORS = {
    "Nature Reviews Genetics": 39.1, "Nat Rev Genet": 39.1,
    "Nature Structural & Molecular Biology": 12.5, "Nature Structural and Molecular Biology": 12.5,
    "Molecular Cell": 14.5, "Mol Cell": 14.5,
    "Genome Biology": 10.1,
    "Epigenetics & Chromatin": 4.2, "Epigenetics and Chromatin": 4.2,
    "Clinical Epigenetics": 4.8,
    "Epigenetics": 2.9,
    "Nature": 50.5,
    "Science": 44.7,
    "Cell": 45.5,
    "Nature Genetics": 31.7, "Nat Genet": 31.7,
    "Cell Reports": 7.5, "Cell Rep": 7.5,
    "Nature Communications": 14.7, "Nat Commun": 14.7,
    "Science Advances": 11.7, "Sci Adv": 11.7,
    "Cancer Discovery": 29.7,
    "Cell Metabolism": 27.7, "Cell Metab": 27.7,
    "Journal of Clinical Investigation": 13.3, "J Clin Invest": 13.3, "JCI": 13.3,
    "Oncogene": 6.9,
    "Cancer Research": 12.5, "Cancer Res": 12.5,
    "Clinical Cancer Research": 10.0, "Clin Cancer Res": 10.0,
    "Nature Reviews Cancer": 72.5, "Nat Rev Cancer": 72.5,
    "Bioinformatics": 4.4,
    "PLOS Computational Biology": 3.8, "PLoS Computational Biology": 3.8, "PLoS Comput Biol": 3.8,
    "Briefings in Bioinformatics": 6.8, "Brief Bioinform": 6.8,
    "Nucleic Acids Research": 16.7, "Nucleic Acids Res": 16.7,
    "Nature Machine Intelligence": 18.8, "Nat Mach Intell": 18.8,
    "Cell Systems": 9.0, "Cell Syst": 9.0,
    "IEEE/ACM Trans. Comp. Bio. & Bioinf.": 3.6, "IEEE/ACM Transactions on Computational Biology and Bioinformatics": 3.6,
    "Journal of Biomedical Informatics": 4.0, "J Biomed Inform": 4.0,
    "Artificial Intelligence in Medicine": 6.1, "Artif Intell Med": 6.1,
    "Patterns": 6.7,
    "Database (Biol. Databases & Curation)": 3.4, "Database": 3.4,
    "GigaScience": 11.8
}

def init_database():
    """初始化SQLite数据库"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 创建搜索历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_date TEXT NOT NULL,
                user_topic TEXT,
                ai_generated_query TEXT,
                final_query TEXT,
                journal_filter TEXT,
                year_range TEXT,
                min_score REAL,
                article_types TEXT,
                total_results INTEGER,
                filtered_results INTEGER,
                search_parameters TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 为现有数据库添加article_types字段（如果不存在）
        try:
            cursor.execute('ALTER TABLE search_history ADD COLUMN article_types TEXT')
        except sqlite3.OperationalError:
            # 字段已存在，忽略错误
            pass
        
        # 创建文章详情表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER,
                pmid TEXT NOT NULL,
                title TEXT,
                journal TEXT,
                journal_abbr TEXT,
                year TEXT,
                volume TEXT,
                issue TEXT,
                pages TEXT,
                doi TEXT,
                abstract TEXT,
                authors TEXT,
                article_types TEXT,
                keywords TEXT,
                citation TEXT,
                pubmed_url TEXT,
                impact_factor REAL,
                score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (search_id) REFERENCES search_history (id),
                UNIQUE(search_id, pmid)
            )
        ''')
        
        # 创建索引以提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_date ON search_history(search_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pmid ON articles(pmid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_id ON articles(search_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_score ON articles(score)')
        
        conn.commit()
        conn.close()
        print("✅ 数据库初始化完成")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

def generate_pubmed_query_with_ai(user_topic):
    """
    使用AI生成PubMed搜索查询字符串
    """
    prompt_xml_md = f"""
<prompt_instructions>
  <role>You are an AI assistant specialized in crafting comprehensive and inclusive PubMed search queries for biomedical research.</role>
  <task>
    Given a user's research topic, generate a PubMed ESearch query that prioritizes RECALL over PRECISION.
    The goal is to capture as many potentially relevant articles as possible, even if some less relevant ones are included.
    It's better to retrieve more articles and let the user filter them, rather than miss important research.
  </task>
  
  <search_philosophy>
    <principle>INCLUSIVE over EXCLUSIVE: Cast a wide net to avoid missing relevant research</principle>
    <principle>BROAD over NARROW: Use OR operators liberally to expand search scope</principle>
    <principle>FLEXIBLE over RIGID: Include variations, synonyms, and related concepts</principle>
    <principle>COMPREHENSIVE over PRECISE: Better to include extra articles than miss key ones</principle>
  </search_philosophy>

  <output_format>
    Return **ONLY** the generated PubMed search string.
    Do not include explanations, introductory text, apologies, or markdown formatting.
    The string should be directly usable as the `term` parameter in a PubMed ESearch API call.

    Example of inclusive output:
    `(telomere OR telomeres OR "telomere length" OR "telomeric DNA" OR telomerase) AND (aging OR ageing OR longevity OR "life span" OR "health span" OR senescence OR "cellular aging")`
  </output_format>

  <guidelines>
    <guideline>1. **Identify ALL Related Concepts**: Extract not just core concepts, but also related, adjacent, and peripheral concepts that researchers might use.</guideline>
    
    <guideline>2. **Maximize Synonym Coverage**: For each concept, include:
        - Scientific terms AND common terms
        - American AND British spellings (e.g., aging/ageing, tumor/tumour)
        - Abbreviations AND full forms
        - Plural AND singular forms
        - Alternative phrasings and expressions
    </guideline>
    
    <guideline>3. **Liberal Use of OR Operators**: 
        - Group synonyms and related terms with OR within parentheses
        - Use OR to connect different ways researchers might describe the same concept
        - Prefer OR over AND when connecting related but distinct concepts
    </guideline>
    
    <guideline>4. **Strategic Use of AND Operators**:
        - Only use AND to connect truly different concept groups
        - Minimize the number of AND connections to avoid over-restriction
        - Consider if concepts could appear in different contexts within the same study
    </guideline>
    
    <guideline>5. **Field Tag Strategy**:
        - Use [tiab] (Title/Abstract) for most terms to capture comprehensive coverage
        - Use [MeSH Terms] sparingly and always with OR alternatives
        - Avoid restrictive field tags that might exclude relevant articles
        - Example: `(diabetes[tiab] OR "diabetes mellitus"[MeSH Terms] OR diabetic[tiab])`
    </guideline>
    
    <guideline>6. **Handle Ambiguous Topics Broadly**:
        - For vague topics, interpret them in multiple possible ways
        - Include both specific and general terms
        - Consider different research contexts and methodologies
        - Example: For "cancer treatment" include: therapy, treatment, intervention, management, care, etc.
    </guideline>
    
    <guideline>7. **Comparative and Qualitative Queries**:
        - For "X vs Y" topics, search for articles mentioning either X OR Y (not necessarily comparing them)
        - For "effectiveness" questions, include: efficacy, effectiveness, outcome, benefit, impact, effect, result
        - For "safety" questions, include: safety, adverse, side effect, toxicity, harm, risk
    </guideline>
    
    <guideline>8. **Temporal and Methodological Inclusivity**:
        - Include terms for different study types: clinical trial, observational, review, meta-analysis, case study
        - Include terms for different populations: human, animal, in vitro, in vivo (unless specifically excluded)
        - Avoid date restrictions in the query itself
    </guideline>
    
    <guideline>9. **Language and Cultural Variations**:
        - Include international terminology variations
        - Consider how different research communities might describe the same phenomenon
        - Include both technical and clinical terminology
    </guideline>
    
    <guideline>10. **Error-Tolerant Construction**:
        - Structure queries to be resilient to minor variations in terminology
        - Use broad categorical terms alongside specific ones
        - Avoid overly complex nested boolean logic that might exclude edge cases
    </guideline>
  </guidelines>

  <examples>
    <example>
      <topic>端粒与衰老</topic>
      <inclusive_query>(telomere OR telomeres OR "telomere length" OR "telomere shortening" OR telomerase OR "telomerase activity" OR "telomeric DNA") AND (aging OR ageing OR longevity OR "life span" OR "health span" OR senescence OR "cellular aging" OR "age-related" OR elderly OR geriatric)</inclusive_query>
    </example>
    
    <example>
      <topic>糖尿病治疗</topic>
      <inclusive_query>(diabetes OR diabetic OR "diabetes mellitus" OR "type 2 diabetes" OR "type 1 diabetes" OR hyperglycemia OR hyperglycaemia) AND (treatment OR therapy OR management OR intervention OR care OR medication OR drug OR insulin OR metformin)</inclusive_query>
    </example>
    
    <example>
      <topic>癌症免疫疗法效果</topic>
      <inclusive_query>(cancer OR tumor OR tumour OR neoplasm OR malignancy OR oncology) AND (immunotherapy OR "immune therapy" OR "checkpoint inhibitor" OR "CAR-T" OR "immune checkpoint" OR immunology) AND (efficacy OR effectiveness OR outcome OR response OR survival OR benefit OR result OR impact)</inclusive_query>
    </example>
  </examples>
</prompt_instructions>

## User's Research Topic:
<user_topic>
{user_topic}
</user_topic>

## Generated Inclusive PubMed Search Query:
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": YOUR_SITE_URL,
        "X-Title": YOUR_SITE_NAME,
    }
    
    data = {
        "model": "anthropic/claude-4.5-sonnet",
        "messages": [{"role": "user", "content": prompt_xml_md}],
        "temperature": 0.4,  # 降低温度以获得更一致的结果
        "top_p": 0.8,        # 稍微降低以提高质量
    }

    print("\n🤖 正在使用AI生成包容性PubMed查询...")
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, data=json.dumps(data), timeout=60)
        response.raise_for_status()
        
        response_json = response.json()
        
        if response_json.get("choices") and len(response_json["choices"]) > 0:
            ai_content = response_json["choices"][0].get("message", {}).get("content", "")
            # 清理响应内容
            ai_content_cleaned = ai_content.strip()
            if ai_content_cleaned.lower().startswith("```pubmed"):
                ai_content_cleaned = ai_content_cleaned[len("```pubmed"):]
            elif ai_content_cleaned.lower().startswith("```"):
                ai_content_cleaned = ai_content_cleaned[len("```"):]

            if ai_content_cleaned.lower().endswith("```"):
                ai_content_cleaned = ai_content_cleaned[:-len("```")]
            
            return ai_content_cleaned.strip()
        else:
            print("❌ AI响应格式错误: 未找到choices或choices数组为空")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 调用OpenRouter API错误: {e}")
        return None
    except Exception as e:
        print(f"❌ AI查询生成时发生意外错误: {e}")
        return None

def search_pubmed_with_simplified_query(original_query, journal=None, min_year=None, max_year=None, main_journals_only=True):
    """当原查询过长时，使用简化查询作为后备方案"""
    print("🔄 正在简化查询以避免URL过长错误...")
    
    # 简化策略：提取核心关键词
    simplified_query = simplify_query(original_query)
    print(f"📝 简化后的查询: {simplified_query}")
    
    # 处理期刊过滤
    search_query = simplified_query
    if journal:
        journals_input_list = journal.replace("、", ",").replace("，", ",").split(",")
        journals_input_list = [j.strip() for j in journals_input_list if j.strip()]
        journal_filter_parts = []
        
        if main_journals_only:
            matched_main_journal_variants = set()
            for j_input in journals_input_list:
                found_main = False
                for main_name_key, variants_list in MAIN_JOURNALS.items():
                    if main_name_key.lower() == j_input.lower() or j_input.lower() in [v.lower() for v in variants_list]:
                        for v in variants_list:
                            matched_main_journal_variants.add(f'"{v}"[journal]')
                        found_main = True
                        break
                
                if not found_main:
                    journal_filter_parts.append(f'"{j_input}"[journal]')
            
            if matched_main_journal_variants:
                journal_filter_parts.extend(list(matched_main_journal_variants))
        else:
            for j_input in journals_input_list:
                journal_filter_parts.append(f'"{j_input}"[journal]')
        
        if journal_filter_parts:
            journal_query_segment = " OR ".join(journal_filter_parts)
            search_query += f" AND ({journal_query_segment})"
    
    # 处理年份过滤
    if min_year and max_year:
        search_query += f" AND {min_year}:{max_year}[pdat]"
    elif min_year:
        search_query += f" AND {min_year}:[pdat]"
    elif max_year:
        search_query += f" AND :{max_year}[pdat]"
    
    # 使用POST请求执行简化查询
    search_url = BASE_URL + "esearch.fcgi"
    search_params = {
        "db": "pubmed", 
        "term": search_query,
        "retmax": 0,
        "usehistory": "y", 
        "api_key": PUBMED_API_KEY
    }
    
    try:
        response = requests.post(search_url, data=search_params, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        error_elem = root.find("ERROR")
        if error_elem is not None and error_elem.text:
            print(f"❌ 简化查询也失败: {error_elem.text}")
            return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}
        
        count_elem = root.find("Count")
        total_count = int(count_elem.text) if count_elem is not None else 0
        print(f"📊 简化查询找到 {total_count} 篇相关文章")
        
        if total_count == 0:
            return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}
        
        # 获取PMIDs
        search_params["retmax"] = min(total_count, 10000)
        response = requests.post(search_url, data=search_params, timeout=60)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        web_env_elem = root.find("WebEnv")
        query_key_elem = root.find("QueryKey")
        
        if web_env_elem is None or query_key_elem is None:
            id_list_direct = [id_elem.text for id_elem in root.findall(".//IdList/Id")]
            if id_list_direct:
                return {"pmids": id_list_direct, "web_env": None, "query_key": None, "total_count": total_count}
            return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}
        
        web_env = web_env_elem.text
        query_key = query_key_elem.text
        id_list = [id_elem.text for id_elem in root.findall(".//IdList/Id")]
        
        print(f"✅ 简化查询成功获取 {len(id_list)} 篇文章的PMIDs")
        return {"pmids": id_list, "web_env": web_env, "query_key": query_key, "total_count": total_count}
        
    except Exception as e:
        print(f"❌ 简化查询失败: {e}")
        return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}

def simplify_query(query):
    """简化复杂的PubMed查询"""
    # 移除过多的OR条件，保留核心关键词
    # 提取主要的AND分组
    and_parts = query.split(" AND ")
    
    simplified_parts = []
    for part in and_parts:
        if part.strip():
            # 对于每个AND部分，如果包含很多OR条件，则简化
            if " OR " in part and part.count(" OR ") > 10:
                # 提取括号内的内容
                if part.startswith("(") and part.endswith(")"):
                    inner_content = part[1:-1]
                    or_terms = [term.strip() for term in inner_content.split(" OR ")]
                    
                    # 保留前5个最重要的术语
                    important_terms = []
                    for term in or_terms[:15]:  # 只取前15个术语
                        if not ("[MeSH Terms]" in term and len(important_terms) > 5):
                            important_terms.append(term)
                        if len(important_terms) >= 8:  # 限制为8个术语
                            break
                    
                    simplified_part = "(" + " OR ".join(important_terms) + ")"
                    simplified_parts.append(simplified_part)
                else:
                    simplified_parts.append(part)
            else:
                simplified_parts.append(part)
    
    simplified_query = " AND ".join(simplified_parts)
    
    # 如果仍然太长，进一步简化
    if len(simplified_query) > 1000:
        # 只保留前两个AND部分
        and_parts = simplified_query.split(" AND ")
        simplified_query = " AND ".join(and_parts[:2])
    
    return simplified_query

def is_main_journal(journal_name):
    """检查期刊是否为主刊"""
    for main_journal_variants in MAIN_JOURNALS.values():
        if any(variant.lower() == journal_name.lower() for variant in main_journal_variants):
            return True
    
    for pattern in SUBSIDIARY_PATTERNS:
        if re.search(pattern, journal_name, re.IGNORECASE):
            for main_journal_variants in MAIN_JOURNALS.values():
                if any(variant.lower() == journal_name.lower() for variant in main_journal_variants):
                    return True
            return False
    return False

def search_pubmed(query, journal=None, min_year=None, max_year=None, main_journals_only=True):
    """搜索PubMed文章，获取所有结果"""
    print(f"📝 原始搜索词: {query}")
    
    # 处理中文标点符号
    query = query.replace("，", " ").replace("、", " ")
    print(f"🔧 处理后的搜索词: {query}")
    
    search_query = query
    
    # 处理期刊过滤
    if journal:
        journals_input_list = journal.replace("、", ",").replace("，", ",").split(",")
        journals_input_list = [j.strip() for j in journals_input_list if j.strip()]
        journal_filter_parts = []
        
        if main_journals_only:
            matched_main_journal_variants = set()
            for j_input in journals_input_list:
                found_main = False
                for main_name_key, variants_list in MAIN_JOURNALS.items():
                    if main_name_key.lower() == j_input.lower() or j_input.lower() in [v.lower() for v in variants_list]:
                        for v in variants_list:
                            matched_main_journal_variants.add(f'"{v}"[journal]')
                        found_main = True
                        break
                
                if not found_main:
                    print(f"⚠️ 警告: '{j_input}' 不在预定义的主刊列表中，但将按字面意思搜索")
                    journal_filter_parts.append(f'"{j_input}"[journal]')
            
            if matched_main_journal_variants:
                journal_filter_parts.extend(list(matched_main_journal_variants))
                print(f"📚 期刊过滤 (主刊模式): {', '.join(journals_input_list)}")
            elif not journal_filter_parts:
                print(f"⚠️ 警告: 用户指定的期刊均未匹配到预定义的主刊列表")
        else:
            for j_input in journals_input_list:
                journal_filter_parts.append(f'"{j_input}"[journal]')
            print(f"📚 期刊过滤 (所有期刊模式): {', '.join(journals_input_list)}")
        
        if journal_filter_parts:
            journal_query_segment = " OR ".join(journal_filter_parts)
            search_query += f" AND ({journal_query_segment})"
    
    # 处理年份过滤
    if min_year and max_year:
        search_query += f" AND {min_year}:{max_year}[pdat]"
        print(f"📅 年份范围: {min_year}-{max_year}")
    elif min_year:
        search_query += f" AND {min_year}:[pdat]"
        print(f"📅 起始年份: {min_year}")
    elif max_year:
        search_query += f" AND :{max_year}[pdat]"
        print(f"📅 截止年份: {max_year}")
    
    if not search_query.strip():
        print("❌ 错误：搜索查询为空。请提供有效的关键词。")
        return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}

    print(f"🔍 最终搜索查询: {search_query}")
    
    # 检查查询长度，决定使用GET还是POST
    search_url = BASE_URL + "esearch.fcgi"
    search_params = {
        "db": "pubmed", 
        "term": search_query,
        "retmax": 0,  # 只获取计数
        "usehistory": "y", 
        "api_key": PUBMED_API_KEY
    }
    
    # 估算URL长度，如果太长则使用POST
    estimated_url_length = len(search_url) + sum(len(f"{k}={v}&") for k, v in search_params.items())
    use_post = estimated_url_length > 2000  # 保守估计，URL长度超过2000字符时使用POST
    
    if use_post:
        print("🔄 查询较长，使用POST请求...")
    
    try:
        # 首先获取总数
        if use_post:
            response = requests.post(search_url, data=search_params, timeout=30)
        else:
            response = requests.get(search_url, params=search_params, timeout=30)
        
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        error_elem = root.find("ERROR")
        if error_elem is not None and error_elem.text:
            print(f"❌ PubMed API错误: {error_elem.text}")
            return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}
        
        count_elem = root.find("Count")
        total_count = int(count_elem.text) if count_elem is not None else 0
        print(f"📊 找到总计 {total_count} 篇相关文章")
        
        if total_count == 0:
            return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}
        
        # 现在获取所有PMIDs
        search_params["retmax"] = min(total_count, 10000)  # PubMed API限制
        
        if use_post:
            response = requests.post(search_url, data=search_params, timeout=60)
        else:
            response = requests.get(search_url, params=search_params, timeout=60)
        
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        web_env_elem = root.find("WebEnv")
        query_key_elem = root.find("QueryKey")
        
        if web_env_elem is None or query_key_elem is None:
            print("⚠️ 搜索响应中缺少WebEnv或QueryKey")
            id_list_direct = [id_elem.text for id_elem in root.findall(".//IdList/Id")]
            if id_list_direct:
                print("🔄 使用直接ID列表作为后备")
                return {"pmids": id_list_direct, "web_env": None, "query_key": None, "total_count": total_count}
            return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}
        
        web_env = web_env_elem.text
        query_key = query_key_elem.text
        id_list = [id_elem.text for id_elem in root.findall(".//IdList/Id")]
        
        print(f"✅ 成功获取 {len(id_list)} 篇文章的PMIDs用于详情提取")
        return {"pmids": id_list, "web_env": web_env, "query_key": query_key, "total_count": total_count}
        
    except requests.exceptions.HTTPError as e:
        if "414" in str(e) or "Request-URI Too Long" in str(e):
            print("⚠️ 查询过长，尝试简化查询...")
            # 尝试简化查询的后备方案
            return search_pubmed_with_simplified_query(query, journal, min_year, max_year, main_journals_only)
        else:
            print(f"❌ HTTP错误: {e}")
            return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}
    except ET.ParseError as e:
        print(f"❌ XML解析错误: {e}")
        # Log the problematic XML content for debugging
        if 'response' in locals() and response is not None:
            try:
                problematic_xml_content = response.content.decode('utf-8', errors='replace')
                print(f"📄 问题XML内容 (前1000字符): {problematic_xml_content[:1000]}")
                # If the error is specific, like line 198, try to log around that area
                lines = problematic_xml_content.splitlines()
                if len(lines) >= 198:
                    start_line = max(0, 198 - 10) # Log 10 lines before
                    end_line = min(len(lines), 198 + 10) # Log 10 lines after
                    print(f"📄 问题XML内容 (行 {start_line + 1} 到 {end_line}):")
                    for i in range(start_line, end_line):
                        print(f"{i+1:03d}: {lines[i]}")
            except Exception as log_e:
                print(f"❌ 记录问题XML时出错: {log_e}")
        return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}
    except Exception as e:
        print(f"❌ 搜索出错: {e}")
        if 'response' in locals() and response is not None:
             print(f"📄 可能相关的响应状态码: {response.status_code}")
        return {"pmids": [], "web_env": None, "query_key": None, "total_count": 0}

def get_element_text_recursive(element):
    """递归获取元素文本内容"""
    if element is None: 
        return ""
    
    text = element.text or ""
    for child in element:
        text += get_element_text_recursive(child)
        if child.tail:
            text += child.tail
    return text.strip()

def fetch_article_details(pmids=None, web_env=None, query_key=None, main_journals_only=True, batch_size=1000):
    """批量获取文章详细信息 - 改进版本"""
    print("🔄 正在获取文章详细信息...")
    
    if not pmids and (not web_env or not query_key):
        print("❌ 错误: 必须提供PMIDs或WebEnv+QueryKey")
        return []
    
    if pmids and len(pmids) == 0 and (not web_env or not query_key):
        print("❌ 没有找到文章ID，无法获取详细信息")
        return []
    
    fetch_url = BASE_URL + "efetch.fcgi"
    all_articles = []
    
    if pmids:
        total_pmids = len(pmids)
        print(f"📄 准备分批获取 {total_pmids} 篇文章详情 (每批 {batch_size} 篇)")
        
        # 分批处理PMIDs
        for i in range(0, total_pmids, batch_size):
            batch_pmids = pmids[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_pmids + batch_size - 1) // batch_size
            
            print(f"⏳ 正在处理第 {batch_num}/{total_batches} 批 ({len(batch_pmids)} 篇文章)...")
            
            # 重试机制
            max_retries = 3
            retry_delay = 2
            
            for retry in range(max_retries):
                try:
                    fetch_params = {
                        "db": "pubmed", 
                        "retmode": "xml", 
                        "api_key": PUBMED_API_KEY,
                        "id": ",".join(batch_pmids)
                    }
                    
                    # Use POST for large batches to avoid URL length limits
                    if len(batch_pmids) > 200:  # Use POST for batches larger than 200
                        response = requests.post(fetch_url, data=fetch_params, timeout=120)
                    else:
                        response = requests.get(fetch_url, params=fetch_params, timeout=120)
                    response.raise_for_status()
                    
                    if not response.content:
                        print(f"⚠️ 第 {batch_num} 批获取到空响应")
                        break
                    
                    root = ET.fromstring(response.content)
                    batch_articles = parse_articles_from_xml(root, main_journals_only)
                    all_articles.extend(batch_articles)
                    
                    print(f"✅ 第 {batch_num} 批完成，获取 {len(batch_articles)} 篇有效文章")
                    break  # 成功则跳出重试循环
                    
                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                    if retry < max_retries - 1:
                        print(f"⚠️ 第 {batch_num} 批网络错误，{retry_delay}秒后重试 ({retry + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        print(f"❌ 第 {batch_num} 批处理失败 (已重试{max_retries}次): {e}")
                        
                except Exception as e:
                    print(f"❌ 第 {batch_num} 批处理失败: {e}")
                    break
            
            # 添加延迟以避免API限制
            if i + batch_size < total_pmids:
                time.sleep(2)  # 稍微增加延迟时间以适应更大的批次
    
    elif web_env and query_key:
        # 使用WebEnv/QueryKey方式
        print("🔄 使用WebEnv/QueryKey方式获取文章详情")
        fetch_params = {
            "db": "pubmed", 
            "retmode": "xml", 
            "api_key": PUBMED_API_KEY,
            "WebEnv": web_env,
            "query_key": query_key,
            "retstart": "0",
            "retmax": "10000"  # 最大限制
        }
        
        try:
            response = requests.get(fetch_url, params=fetch_params, timeout=120)
            response.raise_for_status()
            
            if not response.content:
                print("❌ 获取到空响应")
                return []
            
            root = ET.fromstring(response.content)
            all_articles = parse_articles_from_xml(root, main_journals_only)
            
        except Exception as e:
            print(f"❌ 获取文章详细信息时出错: {e}")
            return []
    
    print(f"🎉 总共成功获取并解析 {len(all_articles)} 篇文章的详细信息")
    return all_articles

def fetch_article_details_with_progress(pmids=None, web_env=None, query_key=None, 
                                      main_journals_only=True, batch_size=1000, 
                                      progress_callback=None):
    """批量获取文章详细信息 - 支持进度回调"""
    print("🔄 正在获取文章详细信息...")
    
    if not pmids and (not web_env or not query_key):
        print("❌ 错误: 必须提供PMIDs或WebEnv+QueryKey")
        return []
    
    if pmids and len(pmids) == 0 and (not web_env or not query_key):
        print("❌ 没有找到文章ID，无法获取详细信息")
        return []
    
    fetch_url = BASE_URL + "efetch.fcgi"
    all_articles = []
    
    if pmids:
        total_pmids = len(pmids)
        print(f"📄 准备分批获取 {total_pmids} 篇文章详情 (每批 {batch_size} 篇)")
        
        # 分批处理PMIDs
        for i in range(0, total_pmids, batch_size):
            batch_pmids = pmids[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_pmids + batch_size - 1) // batch_size
            
            # 更新进度
            if progress_callback:
                progress_callback(i, total_pmids)
            
            print(f"⏳ 正在处理第 {batch_num}/{total_batches} 批 ({len(batch_pmids)} 篇文章)...")
            
            # 重试机制
            max_retries = 3
            retry_delay = 2
            
            for retry in range(max_retries):
                try:
                    fetch_params = {
                        "db": "pubmed", 
                        "retmode": "xml", 
                        "api_key": PUBMED_API_KEY,
                        "id": ",".join(batch_pmids)
                    }
                    
                    # Use POST for large batches to avoid URL length limits
                    if len(batch_pmids) > 200:  # Use POST for batches larger than 200
                        response = requests.post(fetch_url, data=fetch_params, timeout=120)
                    else:
                        response = requests.get(fetch_url, params=fetch_params, timeout=120)
                    response.raise_for_status()
                    
                    if not response.content:
                        print(f"⚠️ 第 {batch_num} 批获取到空响应")
                        break
                    
                    root = ET.fromstring(response.content)
                    batch_articles = parse_articles_from_xml(root, main_journals_only)
                    all_articles.extend(batch_articles)
                    
                    print(f"✅ 第 {batch_num} 批完成，获取 {len(batch_articles)} 篇有效文章")
                    break  # 成功则跳出重试循环
                    
                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                    if retry < max_retries - 1:
                        print(f"⚠️ 第 {batch_num} 批网络错误，{retry_delay}秒后重试 ({retry + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        print(f"❌ 第 {batch_num} 批处理失败 (已重试{max_retries}次): {e}")
                        
                except Exception as e:
                    print(f"❌ 第 {batch_num} 批处理失败: {e}")
                    break
            
            # 添加延迟以避免API限制
            if i + batch_size < total_pmids:
                time.sleep(1)
        
        # 最终进度更新
        if progress_callback:
            progress_callback(total_pmids, total_pmids)
    
    elif web_env and query_key:
        # 使用WebEnv/QueryKey方式
        print("🔄 使用WebEnv/QueryKey方式获取文章详情")
        fetch_params = {
            "db": "pubmed", 
            "retmode": "xml", 
            "api_key": PUBMED_API_KEY,
            "WebEnv": web_env,
            "query_key": query_key,
            "retstart": "0",
            "retmax": "10000"  # 最大限制
        }
        
        try:
            response = requests.get(fetch_url, params=fetch_params, timeout=120)
            response.raise_for_status()
            
            if not response.content:
                print("❌ 获取到空响应")
                return []
            
            root = ET.fromstring(response.content)
            all_articles = parse_articles_from_xml(root, main_journals_only)
            
        except Exception as e:
            print(f"❌ 获取文章详细信息时出错: {e}")
            return []
    
    print(f"🎉 总共成功获取并解析 {len(all_articles)} 篇文章的详细信息")
    return all_articles

def parse_articles_from_xml(root, main_journals_only=True):
    """从XML解析文章信息"""
    articles = []
    
    for article_elem in root.findall(".//PubmedArticle"):
        try:
            pmid_elem = article_elem.find(".//PMID")
            if pmid_elem is None or not pmid_elem.text: 
                continue
            pmid = pmid_elem.text
            
            title_elem = article_elem.find(".//ArticleTitle")
            title = get_element_text_recursive(title_elem) if title_elem is not None else "无标题"
            
            journal_title_elem = article_elem.find(".//Journal/Title")
            journal_name_raw = journal_title_elem.text if journal_title_elem is not None and journal_title_elem.text else "未知期刊"
            
            # 主刊过滤
            if main_journals_only:
                is_target_main_journal = False
                for main_variants_list in MAIN_JOURNALS.values():
                    if any(variant.lower() == journal_name_raw.lower() for variant in main_variants_list):
                        is_target_main_journal = True
                        break
                if not is_target_main_journal: 
                    continue
            
            journal_abbr_elem = article_elem.find(".//Journal/ISOAbbreviation")
            journal_abbr = journal_abbr_elem.text if journal_abbr_elem is not None and journal_abbr_elem.text else ""
            
            # 获取年份
            year_elem = article_elem.find(".//PubDate/Year")
            if year_elem is None or not year_elem.text:
                medline_date_elem = article_elem.find(".//MedlineDate")
                if medline_date_elem is not None and medline_date_elem.text:
                    match = re.search(r"^\d{4}", medline_date_elem.text)
                    year = match.group(0) if match else "未知年份"
                else: 
                    year = "未知年份"
            else: 
                year = year_elem.text
            
            # 获取卷号、期号、页码
            volume_elem = article_elem.find(".//Volume")
            volume = volume_elem.text if volume_elem is not None and volume_elem.text else ""
            
            issue_elem = article_elem.find(".//Issue")
            issue = issue_elem.text if issue_elem is not None and issue_elem.text else ""
            
            pages_elem = article_elem.find(".//MedlinePgn")
            pages = pages_elem.text if pages_elem is not None and pages_elem.text else ""
            
            # 获取DOI
            doi = ""
            for art_id in article_elem.findall(".//ArticleId[@IdType='doi']"):
                doi = art_id.text
                break
            
            # 获取摘要
            abstract_elem = article_elem.find(".//Abstract")
            if abstract_elem is not None:
                abstract_parts_texts = []
                for part_elem in abstract_elem.findall(".//AbstractText"):
                    part_text = get_element_text_recursive(part_elem)
                    if part_text:
                        label = part_elem.get("Label")
                        if label: 
                            abstract_parts_texts.append(f"{label.upper()}: {part_text}")
                        else: 
                            abstract_parts_texts.append(part_text)
                abstract = " ".join(abstract_parts_texts) if abstract_parts_texts else "无摘要"
            else: 
                abstract = "无摘要"
            
            # 获取作者
            authors = []
            author_list = article_elem.findall(".//Author")
            for author_node in author_list:
                last_name_node = author_node.find("LastName")
                fore_name_node = author_node.find("ForeName")
                author_name = ""
                if fore_name_node is not None and fore_name_node.text: 
                    author_name += fore_name_node.text + " "
                if last_name_node is not None and last_name_node.text: 
                    author_name += last_name_node.text
                if author_name.strip(): 
                    authors.append(author_name.strip())
                elif author_node.find("CollectiveName") is not None and author_node.find("CollectiveName").text:
                    authors.append(author_node.find("CollectiveName").text)
            
            # 获取文章类型和关键词
            article_types = [pt.text for pt in article_elem.findall(".//PublicationTypeList/PublicationType") if pt.text]
            keywords = [kw.text for kw in article_elem.findall(".//KeywordList/Keyword") if kw.text]
            
            # 生成引用格式
            citation_authors = ", ".join(authors[:3])
            if len(authors) > 3: 
                citation_authors += ", et al"
            citation = f"{citation_authors}. {title}. {journal_abbr or journal_name_raw}. {year}"
            if volume: 
                citation += f";{volume}"
            if issue: 
                citation += f"({issue})"
            if pages: 
                citation += f":{pages}"
            citation += "."
            if doi: 
                citation += f" doi: {doi}."
            
            # 获取影响因子
            impact_factor = 0.0
            journal_keys_to_try = [journal_name_raw, journal_name_raw.lower()]
            if journal_abbr: 
                journal_keys_to_try.extend([journal_abbr, journal_abbr.lower()])
            
            for key_to_try in journal_keys_to_try:
                if key_to_try in JOURNAL_IMPACT_FACTORS:
                    impact_factor = JOURNAL_IMPACT_FACTORS[key_to_try]
                    break
            
            if impact_factor == 0.0 and journal_name_raw != "未知期刊":
                for jf_key, jf_val in JOURNAL_IMPACT_FACTORS.items():
                    if journal_name_raw.lower() == jf_key.lower():
                         impact_factor = jf_val
                         break
            
            # 构建文章数据
            article_data = {
                "pmid": pmid, 
                "title": title, 
                "journal": journal_name_raw, 
                "journal_abbr": journal_abbr,
                "year": year, 
                "volume": volume, 
                "issue": issue, 
                "pages": pages, 
                "doi": doi,
                "abstract": abstract, 
                "authors": authors, 
                "article_types": article_types,
                "keywords": keywords, 
                "citation": citation,
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "impact_factor": impact_factor
            }
            articles.append(article_data)
            
        except Exception as e:
            print(f"❌ 解析文章PMID {pmid if 'pmid' in locals() else 'Unknown'} 时出错: {e}")
            continue
    
    return articles

def assign_scores_by_if(articles):
    """基于影响因子为文章分配分数"""
    print("📊 正在基于期刊影响因子为文章分配分数...")
    
    for article in articles:
        score = article.get("impact_factor", 0.0)
        article_types = article.get("article_types", [])
        
        # 根据文章类型加分
        if any(re.search("Review", art_type, re.IGNORECASE) for art_type in article_types): 
            score += 8
        if any(re.search(r"Clinical Trial", art_type, re.IGNORECASE) for art_type in article_types) or \
           any(re.search(r"Randomized Controlled Trial", art_type, re.IGNORECASE) for art_type in article_types): 
            score += 7
        if any(re.search(r"Meta-Analysis", art_type, re.IGNORECASE) for art_type in article_types): 
            score += 6
        
        # 根据发表年份加分
        try:
            year_val = int(str(article["year"])[:4])
            current_year = datetime.now().year
            if year_val >= current_year - 2: 
                score += 5
            elif year_val >= current_year - 5: 
                score += 3
        except (ValueError, TypeError): 
            pass
        
        article["score"] = round(score, 2)
    
    # 按分数排序
    articles.sort(key=lambda x: x["score"], reverse=True)
    print("✅ 文章评分完成")
    return articles

def filter_articles(articles, min_score=None):
    """根据最低分数过滤文章"""
    if min_score is None or min_score == 0:
        return articles

    filtered = [article for article in articles if article.get("score", 0) >= min_score]
    print(f"🔍 按最低分数 {min_score} 过滤后，保留 {len(filtered)} 篇文章")
    return filtered

def filter_articles_by_type(articles, article_types=None):
    """根据文章类型过滤文章"""
    if not article_types or 'all' in article_types:
        return articles

    # 过滤掉'all'选项，只保留具体的文章类型
    specific_types = [t for t in article_types if t != 'all']
    if not specific_types:
        return articles

    filtered = []
    for article in articles:
        article_type_list = article.get("article_types", [])
        # 检查文章是否包含任何一个指定的类型
        if any(any(selected_type.lower() in art_type.lower() for art_type in article_type_list)
               for selected_type in specific_types):
            filtered.append(article)

    print(f"📋 按文章类型 {', '.join(specific_types)} 过滤后，保留 {len(filtered)} 篇文章")
    return filtered

def save_search_to_database(search_params, articles):
    """将搜索结果保存到数据库"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 插入搜索历史
        cursor.execute('''
            INSERT INTO search_history
            (search_date, user_topic, ai_generated_query, final_query, journal_filter,
             year_range, min_score, article_types, total_results, filtered_results, search_parameters)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            search_params.get('user_topic', ''),
            search_params.get('ai_generated_query', ''),
            search_params.get('final_query', ''),
            search_params.get('journal_filter', ''),
            search_params.get('year_range', ''),
            search_params.get('min_score', 0.0),
            search_params.get('article_types', '所有类型'),
            search_params.get('total_results', 0),
            len(articles),
            json.dumps(search_params, ensure_ascii=False)
        ))
        
        search_id = cursor.lastrowid
        
        # 插入文章详情
        for article in articles:
            cursor.execute('''
                INSERT OR REPLACE INTO articles 
                (search_id, pmid, title, journal, journal_abbr, year, volume, issue, pages, 
                 doi, abstract, authors, article_types, keywords, citation, pubmed_url, 
                 impact_factor, score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                search_id, article['pmid'], article['title'], article['journal'],
                article.get('journal_abbr', ''), article['year'], article.get('volume', ''),
                article.get('issue', ''), article.get('pages', ''), article.get('doi', ''),
                article['abstract'], json.dumps(article['authors'], ensure_ascii=False),
                json.dumps(article.get('article_types', []), ensure_ascii=False),
                json.dumps(article.get('keywords', []), ensure_ascii=False),
                article['citation'], article['pubmed_url'],
                article.get('impact_factor', 0.0), article.get('score', 0.0)
            ))
        
        conn.commit()
        conn.close()
        print(f"✅ 搜索结果已保存到数据库 (搜索ID: {search_id})")
        return search_id
        
    except Exception as e:
        print(f"❌ 保存到数据库失败: {e}")
        return None

def get_search_history(limit=20):
    """获取搜索历史"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, search_date, user_topic, final_query, journal_filter, 
                   year_range, filtered_results, total_results
            FROM search_history 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'id': row[0],
                'search_date': row[1],
                'user_topic': row[2],
                'final_query': row[3],
                'journal_filter': row[4],
                'year_range': row[5],
                'filtered_results': row[6],
                'total_results': row[7]
            })
        
        conn.close()
        return history
        
    except Exception as e:
        print(f"❌ 获取搜索历史失败: {e}")
        return []

def get_search_by_id(search_id):
    """根据ID获取搜索结果"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 获取搜索信息
        cursor.execute('''
            SELECT * FROM search_history WHERE id = ?
        ''', (search_id,))
        
        search_info = cursor.fetchone()
        if not search_info:
            return None
        
        # 获取文章列表
        cursor.execute('''
            SELECT * FROM articles WHERE search_id = ? ORDER BY score DESC
        ''', (search_id,))
        
        articles = []
        for row in cursor.fetchall():
            article = {
                'pmid': row[2],
                'title': row[3],
                'journal': row[4],
                'journal_abbr': row[5],
                'year': row[6],
                'volume': row[7],
                'issue': row[8],
                'pages': row[9],
                'doi': row[10],
                'abstract': row[11],
                'authors': json.loads(row[12]) if row[12] else [],
                'article_types': json.loads(row[13]) if row[13] else [],
                'keywords': json.loads(row[14]) if row[14] else [],
                'citation': row[15],
                'pubmed_url': row[16],
                'impact_factor': row[17],
                'score': row[18]
            }
            articles.append(article)
        
        conn.close()
        
        return {
            'search_info': search_info,
            'articles': articles
        }
        
    except Exception as e:
        print(f"❌ 获取搜索结果失败: {e}")
        return None

def display_articles_paginated(articles, page_size=50):
    """分页显示文章（命令行版本）"""
    if not articles:
        print("❌ 没有找到符合条件的文章")
        return
    
    total_articles = len(articles)
    total_pages = (total_articles + page_size - 1) // page_size
    
    print(f"\n📚 找到 {total_articles} 篇文章 (已按评分排序)")
    print(f"📄 将以每页 {page_size} 篇的方式展示，共 {total_pages} 页")
    print("="*100)
    
    current_page = 1
    
    while current_page <= total_pages:
        start_idx = (current_page - 1) * page_size
        end_idx = min(start_idx + page_size, total_articles)
        page_articles = articles[start_idx:end_idx]
        
        print(f"\n📖 第 {current_page}/{total_pages} 页 (第 {start_idx + 1}-{end_idx} 篇文章)")
        print("="*100)
        
        for i, article in enumerate(page_articles, start_idx + 1):
            print(f"\n📄 文章 {i}:")
            print(f"  📝 标题: {article['title']}")
            print(f"  👥 作者: {', '.join(article['authors'][:3])}" +
                  (f", et al. ({len(article['authors'])} total)" if len(article['authors']) > 3 else ""))
            print(f"  📰 期刊: {article['journal']} ({article['year']})")
            print(f"  📊 影响因子: {article.get('impact_factor', 'N/A')}")
            print(f"  ⭐ 评分: {article.get('score', 'N/A')}")
            
            article_types = article.get("article_types", [])
            if article_types:
                print(f"  📋 文章类型: {', '.join(article_types[:3])}" +
                      (f" (+{len(article_types)-3} more)" if len(article_types) > 3 else ""))
            
            if article.get("doi"): 
                print(f"  🔗 DOI: {article['doi']}")
            print(f"  🌐 PubMed: {article['pubmed_url']}")
            
            abstract = article['abstract']
            print(f"  📄 摘要: {abstract[:200] + '...' if len(abstract) > 200 else abstract}")
            print("-" * 80)
        
        if current_page < total_pages:
            print(f"\n📄 当前显示第 {current_page}/{total_pages} 页")
            choice = input("请选择操作 (n=下一页, p=上一页, j=跳转到指定页, q=退出浏览): ").lower().strip()
            
            if choice == 'n':
                current_page += 1
            elif choice == 'p' and current_page > 1:
                current_page -= 1
            elif choice == 'j':
                try:
                    target_page = int(input(f"请输入页码 (1-{total_pages}): "))
                    if 1 <= target_page <= total_pages:
                        current_page = target_page
                    else:
                        print("❌ 页码超出范围")
                except ValueError:
                    print("❌ 请输入有效的页码")
            elif choice == 'q':
                break
            else:
                print("❌ 无效选择，请重新输入")
        else:
            print(f"\n✅ 已显示完所有 {total_articles} 篇文章")
            break

def save_to_markdown(articles, filename, query, journal_query_info, year_range):
    """保存结果为Markdown格式"""
    if not articles: 
        print("❌ 没有文章可以保存")
        return False
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# PubMed搜索结果\n\n")
            f.write(f"**搜索关键词**: `{query}`  \n")
            if journal_query_info: 
                f.write(f"**期刊过滤**: {journal_query_info}  \n")
            if year_range: 
                f.write(f"**年份范围**: {year_range}  \n")
            f.write(f"**搜索日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**结果数量**: {len(articles)}篇文章  \n\n")
            
            f.write("## 目录\n\n")
            for i, article in enumerate(articles, 1):
                anchor = re.sub(r'[^\w\s-]', '', article['title'].lower().replace(' ', '-'))
                anchor = re.sub(r'[-\s]+', '-', anchor)[:50]
                f.write(f"{i}. [{article['title']}](#{anchor})  \n")
            
            f.write("\n---\n\n## 文章详情\n\n")
            for i, article in enumerate(articles, 1):
                anchor = re.sub(r'[^\w\s-]', '', article['title'].lower().replace(' ', '-'))
                anchor = re.sub(r'[-\s]+', '-', anchor)[:50]
                f.write(f"### {i}. {article['title']} <a id='{anchor}'></a>\n\n")
                f.write("| 项目 | 内容 |\n| --- | --- |\n")
                f.write(f"| 期刊 | {article['journal']} |\n")
                f.write(f"| 影响因子 | {article.get('impact_factor', 'N/A')} |\n")
                f.write(f"| 年份 | {article['year']} |\n")
                if article.get("volume"): 
                    f.write(f"| 卷号 | {article['volume']} |\n")
                if article.get("issue"): 
                    f.write(f"| 期号 | {article['issue']} |\n")
                if article.get("pages"): 
                    f.write(f"| 页码 | {article['pages']} |\n")
                f.write(f"| 评分 | {article.get('score', 'N/A')} |\n\n")
                f.write(f"**作者**: {', '.join(article['authors'])}\n\n")
                if article.get("article_types"): 
                    f.write(f"**文章类型**: {', '.join(article['article_types'])}\n\n")
                if article.get("keywords"): 
                    f.write(f"**关键词**: {', '.join(article['keywords'])}\n\n")
                f.write(f"**摘要**:  \n{article['abstract']}\n\n")
                f.write("**链接**:  \n")
                if article.get("doi"): 
                    f.write(f"  - DOI: [{article['doi']}](https://doi.org/{article['doi']})  \n")
                f.write(f"  - PubMed: [{article['pmid']}]({article['pubmed_url']})  \n\n")
                f.write(f"**引用格式**:  \n```\n{article['citation']}\n```\n\n---\n\n")
            
            f.write("## 注释\n\n")
            f.write("* 此搜索结果由AI增强型PubMed搜索工具自动生成。\n")
            f.write("* 评分系统基于期刊影响因子、文章类型、发表年份等因素。\n")
            f.write("* 默认仅包含预定义的主刊文章。\n")
        
        print(f"✅ 结果已保存到 {filename}")
        return True
        
    except Exception as e: 
        print(f"❌ 保存Markdown文件时出错: {e}")
        return False

def save_to_json(articles, filename, query, journal_query_info, year_range):
    """保存结果为JSON格式"""
    if not articles: 
        print("❌ 没有文章可以保存")
        return False
    
    try:
        json_data = {
            "search_parameters": {
                "query": query, 
                "journal_filter": journal_query_info, 
                "year_range": year_range,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                "result_count": len(articles)
            }, 
            "articles": articles
        }
        
        with open(filename, 'w', encoding='utf-8') as f: 
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON结果已保存到 {filename}")
        return True
        
    except Exception as e: 
        print(f"❌ 保存JSON文件时出错: {e}")
        return False

# 主搜索函数（命令行版本）
def search_and_filter_pubmed():
    """
    主函数：搜索和过滤PubMed文章，带AI查询生成选项
    """
    # 初始化数据库
    init_database()
    
    print("🚀 欢迎使用AI增强型PubMed搜索工具 - 主刊文章版!")
    print("="*100)
    print("📚 本工具将优先搜索预定义的31种主刊文章 (如Nature, Science, Cell, Lancet等)。")
    print("🤖 您可以输入自然语言主题，由AI生成PubMed查询，或手动输入查询。")
    print("📊 评分系统基于期刊影响因子(IF)，支持Markdown和JSON格式导出。")
    print("💾 所有搜索记录将自动保存到本地数据库。")
    print("="*100)

    # 显示搜索历史选项
    history_choice = input("是否查看最近的搜索历史? (y/n, 默认n): ").lower().strip()
    if history_choice == "y":
        show_search_history()
        print()

    query = ""
    user_topic = ""
    ai_generated_query = ""
    
    use_ai = input("是否使用AI根据您的主题生成PubMed查询? (y/n, 默认y): ").lower().strip()
    if use_ai == "" or use_ai == "y":
        user_topic = input("请输入您的研究主题 (自然语言描述，例如：端粒长度与衰老和长寿的关系研究): ")
        if user_topic:
            ai_generated_query = generate_pubmed_query_with_ai(user_topic)
            if ai_generated_query:
                print("\n💡 AI建议的PubMed查询:")
                print(f"   {ai_generated_query}")
                while True:
                    confirm_ai_query = input("是否使用此查询? (y: 使用 / e: 编辑 / n: 手动输入): ").lower().strip()
                    if confirm_ai_query == 'y':
                        query = ai_generated_query
                        break
                    elif confirm_ai_query == 'e':
                        edited_query = input(f"请编辑查询 (当前: {ai_generated_query}): ")
                        query = edited_query if edited_query.strip() else ai_generated_query
                        break
                    elif confirm_ai_query == 'n':
                        query = ""
                        break
                    else:
                        print("❌ 无效选择，请输入 y, e, 或 n。")
            else:
                print("❌ AI未能生成查询，请手动输入。")
        else:
            print("❌ 未提供研究主题，请手动输入查询。")

    if not query:
        query = input("请输入PubMed搜索关键词 (英文效果更好，支持布尔逻辑): ")

    if not query.strip():
        print("❌ 错误：未提供任何搜索查询。程序退出。")
        return

    default_journals_display = "Nature, Science, Cell, The Lancet, JAMA, NEJM, BMJ"
    journal_input = input(f"请输入目标期刊 (多个用逗号分隔，默认搜索所有预定义主刊): \n(示例: {default_journals_display}): ")
    min_year = input("请输入最早年份 (可选，回车跳过): ").strip()
    max_year = input("请输入最晚年份 (可选，回车跳过): ").strip()
    
    try:
        min_score_input = input("请输入最低分数过滤 (可选，回车跳过，默认0不过滤): ").strip()
        min_score = float(min_score_input) if min_score_input else 0.0
    except ValueError: 
        min_score = 0.0
        print("❌ 最低分数输入无效，不进行分数过滤。")

    year_range_str = ""
    if min_year and max_year: 
        year_range_str = f"{min_year}-{max_year}"
    elif min_year: 
        year_range_str = f"{min_year}以后"
    elif max_year: 
        year_range_str = f"{max_year}以前"
    
    main_journals_only_flag = True
    print("\n🔍 将严格筛选预定义的主刊文章。")
    journal_query_display = journal_input if journal_input else "所有预定义主刊"

    # 开始搜索
    print("\n🚀 开始搜索...")
    search_session = search_pubmed(query, journal_input, min_year, max_year, main_journals_only_flag)
    
    if not search_session["pmids"] and not (search_session["web_env"] and search_session["query_key"]):
        print("❌ 初步搜索未返回任何PMID或有效的搜索会话。请尝试放宽搜索条件。")
        return

    total_found = search_session.get("total_count", 0)
    print(f"📊 搜索完成！找到 {total_found} 篇相关文章")
    
    if total_found == 0:
        print("❌ 未找到任何文章，请尝试其他搜索条件。")
        return

    # 获取文章详情
    articles_detailed = fetch_article_details(
        pmids=search_session.get("pmids"), 
        web_env=search_session.get("web_env"),
        query_key=search_session.get("query_key"), 
        main_journals_only=main_journals_only_flag
    )
    
    if not articles_detailed:
        print("❌ 未能获取到任何符合主刊条件的文章详细信息。")
        return

    print(f"✅ 成功获取 {len(articles_detailed)} 篇主刊文章的详细信息")

    # 评分和过滤
    scored_articles = assign_scores_by_if(articles_detailed)
    final_articles = filter_articles(scored_articles, min_score)
    
    if not final_articles:
        print("❌ 经过所有筛选后，没有文章可供显示。")
        return

    # 保存搜索参数用于数据库存储
    search_params = {
        'user_topic': user_topic,
        'ai_generated_query': ai_generated_query,
        'final_query': query,
        'journal_filter': journal_query_display,
        'year_range': year_range_str,
        'min_score': min_score,
        'total_results': total_found
    }

    # 保存到数据库
    search_id = save_search_to_database(search_params, final_articles)

    # 分页显示文章
    display_articles_paginated(final_articles, page_size=50)

    # 保存文件选项
    print("\n💾 请选择保存格式:")
    print("1. Markdown (.md)  2. JSON (.json)  3. 纯文本 (.txt)  4. Markdown和JSON  5. 不保存")
    save_choice = input("请选择 (默认1): ") or "1"
    
    results_dir = "pubmed_results"
    if not os.path.exists(results_dir): 
        os.makedirs(results_dir)
    
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"pubmed_search_{timestamp_str}"

    if save_choice in ["1", "4"]:
        md_file = os.path.join(results_dir, f"{base_filename}.md")
        save_to_markdown(final_articles, md_file, query, journal_query_display, year_range_str)
    
    if save_choice in ["2", "4"]:
        json_file = os.path.join(results_dir, f"{base_filename}.json")
        save_to_json(final_articles, json_file, query, journal_query_display, year_range_str)
    
    if save_choice == "3":
        txt_file = os.path.join(results_dir, f"{base_filename}.txt")
        try:
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(f"PubMed搜索结果 - 关键词: {query}\n期刊过滤: {journal_query_display}\n")
                if year_range_str: 
                    f.write(f"年份: {year_range_str}\n")
                f.write("="*80 + "\n\n")
                for i, art in enumerate(final_articles, 1):
                    f.write(f"文章 {i}:\n  标题: {art['title']}\n  作者: {', '.join(art['authors'])}\n")
                    f.write(f"  期刊: {art['journal']}, {art['year']}\n")
                    f.write(f"  IF: {art.get('impact_factor', 'N/A')}, Score: {art.get('score', 'N/A')}\n")
                    f.write(f"  摘要: {art['abstract'][:300]}...\n")
                    f.write(f"  PMID: {art['pmid']}, DOI: {art.get('doi', 'N/A')}\n")
                    f.write(f"  Link: {art['pubmed_url']}\n" + "-"*40 + "\n\n")
            print(f"✅ 文本文件已保存到: {txt_file}")
        except Exception as e: 
            print(f"❌ 保存文本文件时出错: {e}")
    
    if save_choice == "5": 
        print("📝 结果未保存到文件。")
    
    # 可选：显示JSON格式
    show_json_console = input("\n是否在控制台显示JSON格式的结果 (前2篇)? (y/n): ").lower()
    if show_json_console == 'y':
        print("\n📄 JSON格式预览 (前2篇):")
        print(json.dumps(final_articles[:min(2, len(final_articles))], ensure_ascii=False, indent=2))

    print(f"\n🎉 搜索完成！本次搜索已保存到数据库 (ID: {search_id})")
    print("感谢使用AI增强型PubMed搜索工具！")

def show_search_history():
    """显示搜索历史"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, search_date, user_topic, final_query, journal_filter, 
                   year_range, filtered_results 
            FROM search_history 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        
        history = cursor.fetchall()
        conn.close()
        
        if not history:
            print("📝 暂无搜索历史")
            return
            
        print("\n📝 最近10次搜索历史:")
        print("="*100)
        for record in history:
            search_id, date, topic, query, journal, year_range, results = record
            print(f"ID: {search_id} | 日期: {date} | 结果数: {results}")
            if topic:
                print(f"  主题: {topic}")
            print(f"  查询: {query}")
            if journal:
                print(f"  期刊: {journal}")
            if year_range:
                print(f"  年份: {year_range}")
            print("-" * 100)
            
    except Exception as e:
        print(f"❌ 获取搜索历史失败: {e}")

if __name__ == "__main__":
    search_and_filter_pubmed()
