import streamlit as st
import trafilatura
import google.generativeai as genai
from openai import OpenAI
import re
import time

# ==========================================
# CẤU HÌNH API KEY
# ==========================================
try:
    # Ưu tiên lấy từ st.secrets nếu chạy trên cloud
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
except:
    # Nếu chạy local, điền key trực tiếp vào đây
    GEMINI_API_KEY = "AIzaSyBLYNskFdd97z-5o-ztZR8SUy72FBUsumE"
    OPENAI_API_KEY = "DÁN_KEY_OPENAI_NẾU_CÓ"

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="LN Reader Pro (Images)", page_icon="🖼️", layout="wide", initial_sidebar_state="collapsed")

# --- QUẢN LÝ STATE (KHỞI TẠO BIẾN) ---
if 'url_input' not in st.session_state: st.session_state['url_input'] = ""
if 'translated_content' not in st.session_state: st.session_state['translated_content'] = ""
if 'auto_run' not in st.session_state: st.session_state['auto_run'] = False
if 'stats_info' not in st.session_state: st.session_state['stats_info'] = ""

# ==========================================
# [MỚI] CÀI ĐẶT HIỂN THỊ (FONT & SIZE)
# ==========================================
with st.expander("⚙️ Cài đặt hiển thị (Font chữ & Kích thước)"):
    c_font, c_size = st.columns(2)
    with c_font:
        font_choice = st.selectbox(
            "Phông chữ",
            ("Merriweather (Sách giấy)", "Segoe UI (Hiện đại)", "Roboto", "Arial", "Times New Roman"),
            index=0 
        )
    with c_size:
        font_size = st.slider("Cỡ chữ (px)", min_value=14, max_value=32, value=20)

# Map tên hiển thị sang tên Font chuẩn CSS
font_family_map = {
    "Merriweather (Sách giấy)": "'Merriweather', serif",
    "Segoe UI (Hiện đại)": "'Segoe UI', sans-serif",
    "Roboto": "'Roboto', sans-serif",
    "Arial": "Arial, sans-serif",
    "Times New Roman": "'Times New Roman', serif"
}
selected_font_css = font_family_map.get(font_choice, "sans-serif")

# --- CSS: DARK MODE & UI FIX (ĐÃ CẬP NHẬT DYNAMIC CSS) ---
st.markdown(f"""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&family=Roboto:wght@300;400;700&display=swap');

    .stApp {{ background-color: #0e1117; }}
    
    /* Box hiển thị nội dung truyện - Dùng biến Python để chỉnh CSS */
    .reading-content {{ 
        font-family: {selected_font_css} !important; 
        font-size: {font_size}px !important; 
        line-height: 1.8 !important; 
        color: #e0e0e0; 
        background-color: #1a1c24; 
        padding: 40px; 
        border-radius: 12px; 
        border: 1px solid #333; 
        margin-top: 20px;
    }}
    
    /* Style cho ảnh trong bài viết */
    .reading-content img {{
        display: block;
        margin: 20px auto;
        max-width: 100%;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }}
    
    /* Caption ảnh (nếu có) */
    .reading-content figure figcaption {{
        text-align: center;
        color: #888;
        font-size: 0.9em;
        margin-top: 5px;
    }}

    .speed-box {{
        background-color: #0f2e1b;
        color: #4caf50;
        padding: 10px 20px;
        border-radius: 8px;
        border: 1px solid #1e4620;
        font-family: monospace;
        font-weight: bold;
        margin-bottom: 10px;
    }}

    .stTextInput input {{ color: #fff !important; background-color: #262730 !important; }}
    div.stButton > button {{ height: 3em; font-weight: bold; }}
</style>
""", unsafe_allow_html=True)

# --- XỬ LÝ ẢNH (MASKING & UNMASKING) ---
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
        placeholder = f"[[IMG_{i}]]"
        html_img = f'<img src="{img_url}" alt="Illustration">'
        if placeholder in restored_text:
            restored_text = restored_text.replace(placeholder, html_img)
        else:
            restored_text += f"\n\n{html_img}"
    return restored_text

# --- CÁC HÀM XỬ LÝ URL ---
def modify_chapter_number(url, step):
    match = re.search(r'(\d+)(?!.*\d)', url)
    if match:
        number_str = match.group(1)
        num = int(number_str) + step
        if num < 1: return url
        new_number_str = str(num).zfill(len(number_str))
        prefix = url[:match.start(1)]
        suffix = url[match.end(1):]
        return f"{prefix}{new_number_str}{suffix}"
    return url

def get_content(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            return trafilatura.extract(downloaded, include_formatting=True, include_images=True) 
        return None
    except:
        return None

# --- XÂY DỰNG PROMPT ---
def build_messages(text, style):
    style_desc = {
        "Kiếm Hiệp / Tiên Hiệp": "Ưu tiên từ Hán Việt. Văn phong cổ trang, hào hùng.",
        "Fantasy / Isekai": "Văn phong hiện đại. Giữ nguyên thuật ngữ game.",
        "Đời thường": "Văn phong nhẹ nhàng, trôi chảy, tự nhiên.",
        "Sắc (R18)": "Mô tả chi tiết, văn phong phóng khoáng."
    }.get(style, "")

    system_prompt = f"""
    Bạn là biên dịch viên Light Novel. Nhiệm vụ: Dịch văn bản sang TIẾNG VIỆT.
    
    QUY TẮC BẮT BUỘC:
    1. Giữ nguyên định dạng Markdown.
    2. TUYỆT ĐỐI KHÔNG DỊCH HAY XÓA CÁC THẺ: [[IMG_0]], [[IMG_1]],... Hãy giữ nguyên chúng ở đúng vị trí.
    3. Phong cách: {style_desc}
    4. Không thêm lời dẫn. Chỉ trả về kết quả dịch.
    """
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Dịch văn bản sau:\n\n{text}"}
    ]

# --- HÀM GỌI MODEL ---
def call_gemini(text, style, model_name):
    try:
        masked_text, images = mask_images(text)
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        msgs = build_messages(masked_text, style)
        full_prompt = msgs[0]['content'] + "\n\n" + msgs[1]['content']
        response = model.generate_content(full_prompt)
        final_html = unmask_images(response.text, images)
        return final_html
    except Exception as e: return f"❌ Lỗi Gemini: {e}"

def call_openai(text, style):
    try:
        masked_text, images = mask_images(text)
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=build_messages(masked_text, style)
        )
        translated_raw = response.choices[0].message.content
        return unmask_images(translated_raw, images)
    except Exception as e: return f"❌ Lỗi OpenAI: {e}"

def call_ollama(text, style, model_name="qwen2.5:7b"):
    try:
        masked_text, images = mask_images(text)
        client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
        response = client.chat.completions.create(
            model=model_name,
            messages=build_messages(masked_text, style),
            temperature=0.3,
            presence_penalty=1.1 
        )
        translated_raw = response.choices[0].message.content
        return unmask_images(translated_raw, images)
    except Exception as e: 
        return f"❌ Lỗi Ollama: {e}"

# --- GIAO DIỆN CHÍNH ---
st.title("🖼️ LN Reader Ultimate (Có Ảnh Minh Họa)")

def trigger_translation(): st.session_state['auto_run'] = True

def handle_nav(step):
    current = st.session_state['url_input']
    if current:
        new_url = modify_chapter_number(current, step)
        if new_url != current:
            st.session_state['url_input'] = new_url
            st.session_state['auto_run'] = True
        else:
            st.toast("⚠️ Không tìm thấy số chương!", icon="🚫")

# INPUT & CONFIG
st.text_input("Link chương truyện:", key="url_input", placeholder="Nhập link...", on_change=trigger_translation)

c1, c2 = st.columns(2)
with c1:
    model_options = [
        "Gemini (gemini-2.5-flash)",
        "Gemini (gemini-flash-latest)",
        "Gemini (gemini-flash-lite-latest)",
        "Gemini (gemini-3-flash-preview)",
        "Gemini (gemma-3-27b-it)",     
        "ChatGPT (gpt-4o-mini)"
    ]
    model_choice = st.selectbox("Engine", model_options)
with c2:
    style_choice = st.selectbox("Style", ("Fantasy / Isekai", "Kiếm Hiệp / Tiên Hiệp", "Đời thường", "Sắc (R18)"))

st.button("🚀 DỊCH & LOAD ẢNH", on_click=trigger_translation, type="primary", use_container_width=True)

# PROCESS
if st.session_state['auto_run'] and st.session_state['url_input']:
    url = st.session_state['url_input']
    with st.spinner(f"⏳ Đang tải văn bản và ảnh từ: {url}..."):
        st.session_state['translated_content'] = ""
        st.session_state['stats_info'] = ""
        
        raw_text = get_content(url)
        
        if raw_text:
            start_time = time.time()
            
            if "Gemini" in model_choice:
                gemini_model_id = model_choice.split("(")[1].replace(")", "")
                final_html = call_gemini(raw_text, style_choice, gemini_model_id)
            elif "ChatGPT" in model_choice:
                final_html = call_openai(raw_text, style_choice)
            else:
                ollama_model = model_choice.split("(")[1].replace(")", "")
                final_html = call_ollama(raw_text, style_choice, ollama_model)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Đếm từ (lược bỏ tag html để đếm cho đúng)
            clean_text = re.sub('<[^<]+?>', '', final_html)
            word_count = len(clean_text.split())
            speed = word_count / duration if duration > 0 else 0
            
            st.session_state['translated_content'] = final_html
            st.session_state['stats_info'] = f"⏱️ {duration:.2f}s | ⚡ {speed:.1f} w/s | 📝 {word_count} từ | 🖼️ Đã xử lý ảnh"
        else:
            st.error("❌ Không lấy được nội dung! (Có thể web chặn bot)")
    st.session_state['auto_run'] = False

# OUTPUT
if st.session_state['translated_content']:
    st.divider()
    if st.session_state['stats_info']:
        st.markdown(f'<div class="speed-box">{st.session_state["stats_info"]}</div>', unsafe_allow_html=True)
    
    # QUAN TRỌNG: allow_html=True để render được thẻ <img>
    st.markdown(f"""
    <div class="reading-content">
        {st.session_state['translated_content']}
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    b1, b2 = st.columns(2)
    with b1: st.button("⬅️ Trước", on_click=handle_nav, args=(-1,), use_container_width=True)
    with b2: st.button("Sau ➡️", on_click=handle_nav, args=(1,), type="primary", use_container_width=True)