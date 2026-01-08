import streamlit as st
import trafilatura
import google.generativeai as genai
from openai import OpenAI
import re
import time
import json
import requests
import urllib3
import warnings

# --- TẮT CẢNH BÁO ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ==========================================
# CẤU HÌNH API KEY & KHO LƯU TRỮ (CLOUD)
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
    
    # Cấu hình JSONBin
    JSONBIN_API_KEY = st.secrets["JSONBIN_API_KEY"]
    JSONBIN_BIN_ID = st.secrets["JSONBIN_BIN_ID"]
    JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
except:
    GEMINI_API_KEY = ""

# --- HÀM XỬ LÝ DỮ LIỆU TRÊN MÂY ---
def load_history_from_cloud():
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    try:
        req = requests.get(JSONBIN_URL, headers=headers)
        if req.status_code == 200:
            data = req.json().get("record", [])
            if isinstance(data, list): return data
            elif isinstance(data, dict):
                return [{'title': "Truyện cũ", 'series': "Unknown", 'chapter': "Chương đã lưu", 'url': url} for url in data.keys()]
    except Exception as e: st.toast(f"Lỗi kết nối Cloud: {e}")
    return []

def save_history_to_cloud(history_list):
    headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY}
    try:
        req = requests.put(JSONBIN_URL, json=history_list, headers=headers)
        if req.status_code != 200: st.toast(f"⚠️ Không lưu được! Code: {req.status_code}")
    except Exception as e: st.toast(f"⚠️ Lỗi lưu Cloud: {e}")

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="LN Reader Cloud", page_icon="☁️", layout="wide", initial_sidebar_state="expanded")

# --- STATE ---
if 'url_input' not in st.session_state: st.session_state['url_input'] = ""
if 'translated_content' not in st.session_state: st.session_state['translated_content'] = ""
if 'auto_run' not in st.session_state: st.session_state['auto_run'] = False
if 'stats_info' not in st.session_state: st.session_state['stats_info'] = ""
if 'force_translate' not in st.session_state: st.session_state['force_translate'] = False

# Load lịch sử từ Cloud
if 'history' not in st.session_state: 
    with st.spinner("Đang đồng bộ dữ liệu từ Cloud..."):
        st.session_state['history'] = load_history_from_cloud()

# --- HÀM HELPER ---
def parse_metadata(raw_title):
    clean_title = re.sub(r'( \| .*?)$', '', raw_title) 
    clean_title = re.sub(r'( - .*? Translation)$', '', clean_title); clean_title = re.sub(r'( - .*? Novel)$', '', clean_title)
    series_name = clean_title; chapter_name = "Đọc ngay"
    match_a = re.search(r'(.*?)\s*[-|–]\s*(Chapter \d+.*|Chương \d+.*|Vol \d+.*)', clean_title, re.IGNORECASE)
    match_b = re.search(r'(Chapter \d+.*|Chương \d+.*|Vol \d+.*)\s*[-|–]\s*(.*)', clean_title, re.IGNORECASE)
    if match_a: series_name = match_a.group(1).strip(); chapter_name = match_a.group(2).strip()
    elif match_b: chapter_name = match_b.group(1).strip(); series_name = match_b.group(2).strip()
    else:
        split_match = re.search(r'(.*?) (Chapter \d+|Chương \d+)(.*)', clean_title, re.IGNORECASE)
        if split_match: series_name = split_match.group(1).strip(); chapter_name = split_match.group(2).strip() + split_match.group(3).strip()
    return series_name, chapter_name

# [MỚI] Hàm xóa từng chương
def delete_chapter(target_url):
    # Lọc bỏ chương có URL trùng khớp
    st.session_state['history'] = [item for item in st.session_state['history'] if item.get('url') != target_url]
    # Lưu lại lên Cloud ngay lập tức
    save_history_to_cloud(st.session_state['history'])
    st.toast("Đã xóa chương khỏi thư viện!", icon="🗑️")

# --- SIDEBAR ---
with st.sidebar:
    st.title("☁️ Thư viện Cloud")
    with st.expander("⚙️ Cài đặt", expanded=False):
        font_choice = st.selectbox("Phông chữ", ("Merriweather (Sách giấy)", "Literata (E-book)", "Be Vietnam Pro (Hiện đại)", "Nunito (Êm mắt)", "Lora (Thơ mộng)", "Roboto"), index=0)
        font_family_map = {
            "Merriweather (Sách giấy)": "'Merriweather', serif", "Literata (E-book)": "'Literata', serif",
            "Be Vietnam Pro (Hiện đại)": "'Be Vietnam Pro', sans-serif", "Nunito (Êm mắt)": "'Nunito', sans-serif",
            "Lora (Thơ mộng)": "'Lora', serif", "Roboto": "'Roboto', sans-serif"
        }
        st.markdown(f"<style>@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@300;400;700&family=Literata:opsz,wght@7..72,300;7..72,400&family=Lora:wght@400;700&family=Merriweather:wght@300;400;700&family=Nunito:wght@300;400;700&family=Roboto:wght@300;400;700&display=swap');</style>", unsafe_allow_html=True)
        font_size = st.slider("Cỡ chữ", 14, 32, 20)
    
    st.divider()
    
    # Nút xóa tất cả (để xuống dưới cùng hoặc giữ lại tùy bạn)
    if st.button("🚨 Xóa TOÀN BỘ thư viện", help="Cẩn thận! Hành động này không thể hoàn tác"):
        st.session_state['history'] = []
        save_history_to_cloud([])
        st.rerun()

    st.subheader("🕒 Lịch sử")
    
    # Hiển thị list (Mới nhất lên đầu)
    display_list = list(reversed(st.session_state['history']))[:30]
    
    for i, item in enumerate(display_list):
        url = item.get('url', '')
        series = item.get('series', 'Truyện')
        chapter = item.get('chapter', 'Chương ?')
        
        # Cắt ngắn tên truyện
        short_series = (series[:22] + '..') if len(series) > 22 else series
        
        has_content = 'content' in item and item['content']
        icon = "💾" if has_content else "☁️"
        
        with st.container():
            st.markdown(f"**📖 {short_series}**")
            
            # [MỚI] Chia cột: 4 phần cho nút đọc, 1 phần cho nút xóa
            col_read, col_del = st.columns([4, 1])
            
            with col_read:
                if st.button(f"{icon} {chapter}", key=f"read_{i}", help=url, use_container_width=True):
                    st.session_state['url_input'] = url
                    st.session_state['auto_run'] = True
                    st.session_state['force_translate'] = False
                    st.rerun()
            
            with col_del:
                # Nút xóa nhỏ
                if st.button("🗑️", key=f"del_{i}", help="Xóa chương này", use_container_width=True):
                    delete_chapter(url)
                    st.rerun()
            
            st.markdown("---")

# --- CSS & CRAWL LOGIC ---
selected_css = font_family_map.get(font_choice, "sans-serif")
st.markdown(f"""
<style>
    .stApp {{ background-color: #0e1117; }}
    .reading-content {{ font-family: {selected_css} !important; font-size: {font_size}px !important; line-height: 1.8 !important; color: #e0e0e0; background-color: #1a1c24; padding: 40px; border-radius: 12px; border: 1px solid #333; margin-top: 20px; }}
    .reading-content img {{ display: block; margin: 20px auto; max-width: 100%; border-radius: 8px; }}
    .reading-content figure figcaption {{ text-align: center; color: #888; font-size: 0.9em; }}
    div.stButton > button {{ border-radius: 6px; }}
    /* Tùy chỉnh nút xóa cho đẹp */
    div[data-testid="column"] button[kind="secondary"] {{ padding: 0.25rem 0.5rem; }}
</style>
""", unsafe_allow_html=True)

def mask_images(text):
    image_pattern = r'!\[.*?\]\((.*?)\)'
    images = re.findall(image_pattern, text)
    masked_text = text
    for i, img_url in enumerate(images): masked_text = re.sub(r'!\[.*?\]\(' + re.escape(img_url) + r'\)', f'\n\n[[IMG_{i}]]\n\n', masked_text, count=1)
    return masked_text, images

def unmask_images(text, images):
    restored_text = text
    for i, img_url in enumerate(images):
        html_img = f'<img src="{img_url}" alt="Minh họa">'
        if f"[[IMG_{i}]]" in restored_text: restored_text = restored_text.replace(f"[[IMG_{i}]]", html_img)
        else: restored_text += f"\n\n{html_img}"
    return restored_text

def get_content_data(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Referer': 'https://www.google.com/'}
    try:
        html_content = None
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200: html_content = response.text
        if not html_content: html_content = trafilatura.fetch_url(url)
        if html_content:
            data = trafilatura.bare_extraction(html_content, include_formatting=True, include_images=True, url=url)
            if data:
                if isinstance(data, dict): raw_title = data.get("title", "Không tiêu đề"); text_content = data.get("text", "")
                else: raw_title = getattr(data, "title", "Không tiêu đề"); text_content = getattr(data, "text", "")
                if not text_content: return None
                series, chapter = parse_metadata(str(raw_title))
                return {"raw_title": str(raw_title), "series": series, "chapter": chapter, "text": str(text_content)}
    except Exception as e: print(f"Crawl error: {e}")
    return None

def build_messages(text, style):
    style_desc = {"Kiếm Hiệp / Tiên Hiệp": "Hán Việt, cổ trang.", "Fantasy / Isekai": "Hiện đại, giữ term game.", "Đời thường": "Tự nhiên, nhẹ nhàng.", "Sắc (R18)": "Mô tả chi tiết."}.get(style, "")
    return [{"role": "system", "content": f"Dịch sang TIẾNG VIỆT. Phong cách: {style_desc}. Giữ nguyên Markdown và thẻ [[IMG_x]]."}, {"role": "user", "content": text}]

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
    except Exception as e: return f"❌ Lỗi AI: {e}"

def modify_chapter(url, step):
    match = re.search(r'(\d+)(?!.*\d)', url)
    if match:
        num_str = match.group(1); new_num = str(int(num_str) + step).zfill(len(num_str))
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
            st.session_state['force_translate'] = False 
            st.rerun() 
        else: st.toast("Không tìm thấy số chương!")

def force_retranslate():
    st.session_state['force_translate'] = True
    st.session_state['auto_run'] = True

def trigger_run(): 
    st.session_state['auto_run'] = True
    st.session_state['force_translate'] = False

# --- MAIN UI ---
st.title("☁️ AI Light Novel Reader (Cloud)")
st.text_input("Link chương truyện:", key="url_input", on_change=trigger_run, placeholder="Nhập link...")
c1, c2 = st.columns(2)
with c1: model_sel = st.selectbox("Engine", ["Gemini (gemini-2.5-flash)", "Gemini (gemini-flash-latest)", "Gemini (gemini-flash-lite-latest)", "Gemini (gemini-3-flash-preview)", "Gemini (gemma-3-27b-it)", "ChatGPT (gpt-4o-mini)"])
with c2: style_sel = st.selectbox("Style", ("Fantasy / Isekai", "Kiếm Hiệp / Tiên Hiệp", "Đời thường", "Sắc (R18)"))
st.button("🚀 DỊCH NGAY", on_click=trigger_run, type="primary", use_container_width=True)

# ========================================================
# LOGIC THỰC THI
# ========================================================
if st.session_state['auto_run'] and st.session_state['url_input']:
    url = st.session_state['url_input']
    
    # Check Cache
    if not st.session_state['force_translate']:
        cached_entry = next((item for item in st.session_state['history'] if item.get('url') == url), None)
    else: cached_entry = None
    
    # [A] Load Offline
    if cached_entry and 'content' in cached_entry and cached_entry['content']:
        st.toast("⚡ Đã tải từ Cloud (Offline)", icon="💾")
        st.session_state['translated_content'] = cached_entry['content']
        st.session_state['stats_info'] = "☁️ Đọc từ Cloud Storage"
        st.divider()
        st.warning("⚠️ Bạn đang đọc bản lưu Offline.")
        st.button("🔄 Dịch lại chương này (Bỏ qua Cache)", on_click=force_retranslate, use_container_width=True)
    
    # [B] Dịch Mới
    else:
        with st.spinner(f"⏳ Đang tải và dịch: {url}..."):
            data = get_content_data(url)
            if data and data['text']:
                start = time.time()
                final_html = call_ai(data['text'], style_sel, model_sel)
                dur = time.time() - start
                wc = len(re.sub('<[^<]+?>', '', final_html).split())
                full_content = f"<h3>{data['series']}</h3><h4>{data['chapter']}</h4><hr>{final_html}"
                
                # Cập nhật & Lưu
                new_entry = {'title': data['raw_title'], 'series': data['series'], 'chapter': data['chapter'], 'url': url, 'content': full_content}
                st.session_state['history'] = [item for item in st.session_state['history'] if isinstance(item, dict) and item.get('url') != url]
                st.session_state['history'].append(new_entry)
                save_history_to_cloud(st.session_state['history'])
                
                st.session_state['translated_content'] = full_content
                st.session_state['stats_info'] = f"⏱️ {dur:.2f}s | 📝 {wc} từ | 💾 Đã lưu Cloud"
                st.session_state['force_translate'] = False
            else: st.error("❌ Lỗi tải nội dung!")
    st.session_state['auto_run'] = False

# --- OUTPUT ---
if st.session_state['translated_content']:
    st.divider()
    if st.session_state['stats_info']: st.markdown(f'<div class="speed-box">{st.session_state["stats_info"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="reading-content">{st.session_state["translated_content"]}</div>', unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    with b1: st.button("⬅️ Chương trước", on_click=nav_click, args=(-1,), use_container_width=True)
    with b2: st.button("Chương sau ➡️", on_click=nav_click, args=(1,), type="primary", use_container_width=True)