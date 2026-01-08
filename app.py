import streamlit as st
import trafilatura
import google.generativeai as genai
from openai import OpenAI
import re
import time
import json
import os
import requests
import urllib3
import warnings

# --- TẮT CẢNH BÁO RÁC ---
# Tắt cảnh báo SSL khi dùng verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Tắt cảnh báo thư viện cũ của Google (để đỡ rối mắt)
warnings.filterwarnings("ignore", category=FutureWarning)

# ==========================================
# CẤU HÌNH API KEY
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
except:
    GEMINI_API_KEY = ""

HISTORY_FILE = "translation_history.json"

# --- HÀM XỬ LÝ FILE JSON ---
def load_history_from_file():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [{'title': "Truyện cũ", 'series': "Không rõ", 'chapter': "Chương đã lưu", 'url': url} for url in data.keys()]
        except: return []
    return []

def save_history_to_file(history_list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_list, f, ensure_ascii=False, indent=4)
    except Exception as e: st.toast(f"Lỗi lưu file: {e}")

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="LN Reader Ultimate", page_icon="📚", layout="wide", initial_sidebar_state="expanded")

# --- STATE ---
if 'url_input' not in st.session_state: st.session_state['url_input'] = ""
if 'translated_content' not in st.session_state: st.session_state['translated_content'] = ""
if 'auto_run' not in st.session_state: st.session_state['auto_run'] = False
if 'stats_info' not in st.session_state: st.session_state['stats_info'] = ""
if 'history' not in st.session_state: st.session_state['history'] = load_history_from_file()

# --- HÀM TÁCH TÊN TRUYỆN & CHƯƠNG ---
def parse_metadata(raw_title):
    clean_title = re.sub(r'( \| .*?)$', '', raw_title) 
    clean_title = re.sub(r'( - .*? Translation)$', '', clean_title)
    clean_title = re.sub(r'( - .*? Novel)$', '', clean_title)

    series_name = clean_title
    chapter_name = "Đọc ngay"

    match_a = re.search(r'(.*?)\s*[-|–]\s*(Chapter \d+.*|Chương \d+.*|Vol \d+.*)', clean_title, re.IGNORECASE)
    match_b = re.search(r'(Chapter \d+.*|Chương \d+.*|Vol \d+.*)\s*[-|–]\s*(.*)', clean_title, re.IGNORECASE)

    if match_a:
        series_name = match_a.group(1).strip()
        chapter_name = match_a.group(2).strip()
    elif match_b:
        chapter_name = match_b.group(1).strip()
        series_name = match_b.group(2).strip()
    else:
        split_match = re.search(r'(.*?) (Chapter \d+|Chương \d+)(.*)', clean_title, re.IGNORECASE)
        if split_match:
            series_name = split_match.group(1).strip()
            chapter_name = split_match.group(2).strip() + split_match.group(3).strip()

    return series_name, chapter_name

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.title("🗂️ Thư viện")
    
    with st.expander("⚙️ Cài đặt", expanded=False):
        font_choice = st.selectbox(
            "Phông chữ",
            ("Merriweather (Sách giấy)", "Literata (E-book)", "Be Vietnam Pro (Hiện đại)", "Nunito (Êm mắt)", "Lora (Thơ mộng)", "Roboto"),
            index=0
        )
        font_family_map = {
            "Merriweather (Sách giấy)": "'Merriweather', serif",
            "Literata (E-book)": "'Literata', serif",
            "Be Vietnam Pro (Hiện đại)": "'Be Vietnam Pro', sans-serif",
            "Nunito (Êm mắt)": "'Nunito', sans-serif",
            "Lora (Thơ mộng)": "'Lora', serif",
            "Roboto": "'Roboto', sans-serif"
        }
        st.markdown(f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@300;400;700&family=Literata:opsz,wght@7..72,300;7..72,400&family=Lora:wght@400;700&family=Merriweather:wght@300;400;700&family=Nunito:wght@300;400;700&family=Roboto:wght@300;400;700&display=swap');
    
            /* ... các css khác giữ nguyên ... */
        </style>
""", unsafe_allow_html=True)
        font_size = st.slider("Cỡ chữ", 14, 32, 20)
    
    st.divider()
    
    c1, c2 = st.columns([3, 1])
    c1.subheader("🕒 Lịch sử")
    if c2.button("🗑️", help="Xóa sạch"):
        st.session_state['history'] = []
        save_history_to_file([])
        st.rerun()

    display_list = list(reversed(st.session_state['history']))[:30]
    
    for i, item in enumerate(display_list):
        url = item.get('url', '')
        series = item.get('series', item.get('title', 'Truyện Không Tên'))
        chapter = item.get('chapter', 'Chương ?')
        display_series = (series[:28] + '..') if len(series) > 28 else series
        
        with st.container():
            st.markdown(f"**📖 {display_series}**")
            if st.button(f"👉 {chapter}", key=f"h_{i}", help=url, use_container_width=True):
                st.session_state['url_input'] = url
                st.session_state['auto_run'] = True
                st.rerun()
            st.markdown("---")

# --- CSS ---
font_map = {"Merriweather (Sách giấy)": "'Merriweather', serif", "Segoe UI (Hiện đại)": "'Segoe UI', sans-serif", "Roboto": "'Roboto', sans-serif", "Arial": "Arial, sans-serif"}
selected_css = font_map.get(font_choice, "sans-serif")

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&family=Roboto:wght@300;400;700&display=swap');
    .stApp {{ background-color: #0e1117; }}
    .reading-content {{ 
        font-family: {selected_css} !important; font-size: {font_size}px !important; 
        line-height: 1.8 !important; color: #e0e0e0; background-color: #1a1c24; 
        padding: 40px; border-radius: 12px; border: 1px solid #333; margin-top: 20px;
    }}
    .reading-content img {{ display: block; margin: 20px auto; max-width: 100%; border-radius: 8px; }}
    .reading-content figure figcaption {{ text-align: center; color: #888; font-size: 0.9em; }}
    div.stButton > button {{ border-radius: 6px; }}
    .stMarkdown p {{ margin-bottom: 0px; }}
</style>
""", unsafe_allow_html=True)

# --- CORE LOGIC ---
def mask_images(text):
    image_pattern = r'!\[.*?\]\((.*?)\)'
    images = re.findall(image_pattern, text)
    masked_text = text
    for i, img_url in enumerate(images):
        masked_text = re.sub(r'!\[.*?\]\(' + re.escape(img_url) + r'\)', f'\n\n[[IMG_{i}]]\n\n', masked_text, count=1)
    return masked_text, images

def unmask_images(text, images):
    restored_text = text
    for i, img_url in enumerate(images):
        html_img = f'<img src="{img_url}" alt="Minh họa">'
        if f"[[IMG_{i}]]" in restored_text:
            restored_text = restored_text.replace(f"[[IMG_{i}]]", html_img)
        else: restored_text += f"\n\n{html_img}"
    return restored_text

# ========================================================
# [ĐÃ SỬA LỖI] HÀM CRAWL CHẤP HẾT MỌI LOẠI DATA TRẢ VỀ
# ========================================================
def get_content_data(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        html_content = None
        # Ưu tiên requests để fake header
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            html_content = response.text
        
        # Nếu requests tạch, thử trafilatura fetch
        if not html_content:
            html_content = trafilatura.fetch_url(url)

        if html_content:
            # Lấy dữ liệu thô
            data = trafilatura.bare_extraction(html_content, include_formatting=True, include_images=True, url=url)
            
            if data:
                # [QUAN TRỌNG] Kiểm tra kiểu dữ liệu để tránh lỗi 'Document object has no attribute get'
                if isinstance(data, dict):
                    raw_title = data.get("title", "Không tiêu đề")
                    text_content = data.get("text", "")
                else:
                    # Nếu là Object (Document), dùng getattr để lấy
                    raw_title = getattr(data, "title", "Không tiêu đề")
                    text_content = getattr(data, "text", "")

                # Nếu text rỗng thì coi như lỗi
                if not text_content:
                    return None

                # Tách tên truyện và chương
                series, chapter = parse_metadata(str(raw_title))
                
                return {
                    "raw_title": str(raw_title),
                    "series": series,
                    "chapter": chapter,
                    "text": str(text_content)
                }
    except Exception as e:
        print(f"Crawl error: {e}")
        # Không throw lỗi ra màn hình để tránh làm user sợ, chỉ in ra console
    return None

def build_messages(text, style):
    style_desc = {
        "Kiếm Hiệp / Tiên Hiệp": "Hán Việt, cổ trang.",
        "Fantasy / Isekai": "Hiện đại, giữ term game.",
        "Đời thường": "Tự nhiên, nhẹ nhàng.",
        "Sắc (R18)": "Mô tả chi tiết."
    }.get(style, "")
    return [{"role": "system", "content": f"Dịch sang TIẾNG VIỆT. Phong cách: {style_desc}. Giữ nguyên Markdown và thẻ [[IMG_x]]."}, 
            {"role": "user", "content": text}]

def call_ai(text, style, model_name):
    masked, imgs = mask_images(text)
    try:
        if "Gemini" in model_name:
            m_id = model_name.split("(")[1].replace(")", "")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(m_id)
            msgs = build_messages(masked, style)
            res = model.generate_content(msgs[0]['content'] + "\n" + msgs[1]['content'])
            return unmask_images(res.text, imgs)
        elif "ChatGPT" in model_name:
            client = OpenAI(api_key=OPENAI_API_KEY)
            res = client.chat.completions.create(model="gpt-4o-mini", messages=build_messages(masked, style))
            return unmask_images(res.choices[0].message.content, imgs)
        else: # Ollama
            m_id = model_name.split("(")[1].replace(")", "")
            client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
            res = client.chat.completions.create(model=m_id, messages=build_messages(masked, style), temperature=0.3)
            return unmask_images(res.choices[0].message.content, imgs)
    except Exception as e: return f"❌ Lỗi AI: {e}"

def modify_chapter(url, step):
    match = re.search(r'(\d+)(?!.*\d)', url)
    if match:
        num_str = match.group(1)
        new_num = str(int(num_str) + step).zfill(len(num_str))
        if int(new_num) < 1: return url
        return url[:match.start(1)] + new_num + url[match.end(1):]
    return url

def nav_click(step):
    current = st.session_state['url_input']
    if current:
        new = modify_chapter(current, step)
        if new != current:
            st.session_state['url_input'] = new
            st.session_state['auto_run'] = True
        else: st.toast("Không tìm thấy số chương!")

def trigger_run(): st.session_state['auto_run'] = True

# --- MAIN UI ---
st.title("📚 AI Light Novel Reader")

st.text_input("Link chương truyện:", key="url_input", on_change=trigger_run, placeholder="Nhập link...")

c1, c2 = st.columns(2)
with c1:
    m_opt = [
        "Gemini (gemini-2.5-flash)",
        "Gemini (gemini-flash-latest)",
        "Gemini (gemini-flash-lite-latest)",
        "Gemini (gemini-3-flash-preview)",
        "Gemini (gemma-3-27b-it)",     
        "ChatGPT (gpt-4o-mini)"
    ]
    model_sel = st.selectbox("Engine", m_opt)
with c2:
    style_sel = st.selectbox("Style", ("Fantasy / Isekai", "Kiếm Hiệp / Tiên Hiệp", "Đời thường", "Sắc (R18)"))

st.button("🚀 DỊCH NGAY", on_click=trigger_run, type="primary", use_container_width=True)

# --- EXECUTION ---
if st.session_state['auto_run'] and st.session_state['url_input']:
    url = st.session_state['url_input']
    
    with st.spinner(f"⏳ Đang tải và phân tích: {url}..."):
        data = get_content_data(url)
        
        if data and data['text']:
            new_entry = {
                'title': data['raw_title'],
                'series': data['series'],
                'chapter': data['chapter'],
                'url': url
            }
            
            st.session_state['history'] = [item for item in st.session_state['history'] if isinstance(item, dict) and item.get('url') != url]
            st.session_state['history'].append(new_entry)
            save_history_to_file(st.session_state['history'])
            
            start = time.time()
            final_html = call_ai(data['text'], style_sel, model_sel)
            dur = time.time() - start
            wc = len(re.sub('<[^<]+?>', '', final_html).split())
            
            header_html = f"<h3>{data['series']}</h3><h4>{data['chapter']}</h4><hr>"
            st.session_state['translated_content'] = header_html + final_html
            st.session_state['stats_info'] = f"⏱️ {dur:.2f}s | 📝 {wc} từ"
        else:
            st.error("❌ Không lấy được nội dung! (Web chặn bot hoặc link chết)")
            
    st.session_state['auto_run'] = False

# --- OUTPUT AREA ---
if st.session_state['translated_content']:
    st.divider()
    if st.session_state['stats_info']: st.markdown(f'<div class="speed-box">{st.session_state["stats_info"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="reading-content">{st.session_state["translated_content"]}</div>', unsafe_allow_html=True)
    
    b1, b2 = st.columns(2)
    with b1: st.button("⬅️ Chương trước", on_click=nav_click, args=(-1,), use_container_width=True)
    with b2: st.button("Chương sau ➡️", on_click=nav_click, args=(1,), type="primary", use_container_width=True)