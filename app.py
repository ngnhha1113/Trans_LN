import streamlit as st

import google.generativeai as genai
from openai import OpenAI
import re
import time

# ==========================================
# CẤU HÌNH API KEY (Điền key của bạn vào đây)
# ==========================================
# Lưu ý: Thay API Key thật của bạn vào đây
# MỚI (Dùng st.secrets)
# Nếu chạy trên máy local mà lỗi, nó sẽ báo cần tạo file secrets.toml, 
# nhưng khi lên web nó sẽ tự lấy từ cấu hình server.
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    
except:
    st.error("Chưa cấu hình API Key trong Secrets!")
    st.stop()

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="LN Reader Ultimate", page_icon="📖", layout="wide", initial_sidebar_state="collapsed")

# --- CSS: DARK MODE & UI FIX ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    
    /* Box hiển thị nội dung truyện */
    .reading-content { 
        font-family: 'Segoe UI', 'Roboto', sans-serif; 
        font-size: 19px !important; 
        line-height: 1.8 !important; 
        color: #e0e0e0; 
        background-color: #1a1c24; 
        padding: 40px; 
        border-radius: 12px; 
        border: 1px solid #333; 
        margin-top: 20px;
    }

    /* Box hiển thị thông tin tốc độ */
    .speed-box {
        background-color: #0f2e1b;
        color: #4caf50;
        padding: 10px 20px;
        border-radius: 8px;
        border: 1px solid #1e4620;
        font-family: monospace;
        font-weight: bold;
        margin-bottom: 10px;
    }

    .stTextInput input { color: #fff !important; background-color: #262730 !important; }
    div.stButton > button { height: 3em; font-weight: bold; }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- CÁC HÀM XỬ LÝ URL ---
def modify_chapter_number(url, step):
    match = re.search(r'(\d+)(?!.*\d)', url)
    if match:
        number_str = match.group(1)
        # Giữ nguyên số 0 ở đầu (ví dụ 01, 02)
        format_str = f"{{:0{len(number_str)}d}}"
        num = int(number_str) + step
        if num < 1: return url
        
        new_number_str = str(num).zfill(len(number_str))
        prefix = url[:match.start(1)]
        suffix = url[match.end(1):]
        return f"{prefix}{new_number_str}{suffix}"
    return url

def get_content(url):
    try:
        # User-agent giả lập để tránh bị chặn
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            return trafilatura.extract(downloaded, include_formatting=True) 
        return None
    except:
        return None

# --- XÂY DỰNG PROMPT (QUAN TRỌNG) ---
def build_messages(text, style):
    style_desc = {
        "Kiếm Hiệp / Tiên Hiệp": "Ưu tiên từ Hán Việt (huynh đệ, tại hạ, pháp bảo). Văn phong cổ trang, hào hùng.",
        "Fantasy / Isekai": "Văn phong hiện đại. Giữ nguyên thuật ngữ game (Skill, Level, Rank).",
        "Đời thường": "Văn phong nhẹ nhàng, trôi chảy, ngôn ngữ tự nhiên.",
        "Sắc (R18)": "Mô tả chi tiết, văn phong phóng khoáng, gợi cảm."
    }.get(style, "")

    # Prompt được tối ưu để chống lỗi trả về tiếng Trung
    system_prompt = f"""
    NHIỆM VỤ: Bạn là một dịch giả chuyên nghiệp. Hãy dịch văn bản được cung cấp sang TIẾNG VIỆT.
    
    YÊU CẦU BẮT BUỘC:
    1. NGÔN NGỮ ĐÍCH: CHỈ DÙNG TIẾNG VIỆT. Tuyệt đối KHÔNG trả về tiếng Trung, tiếng Anh hay tiếng Nhật.
    2. Nếu văn bản gốc có chứa tiếng Trung/Nhật, hãy dịch toàn bộ ý nghĩa sang tiếng Việt mượt mà.
    3. PHONG CÁCH: {style_desc}
    4. ĐỊNH DẠNG: Trả về dạng Markdown chuẩn. Giữ nguyên các đoạn xuống dòng.
    5. KHÔNG giải thích, KHÔNG thêm lời dẫn (ví dụ: "Đây là bản dịch..."). Chỉ trả về kết quả dịch.
    """
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Dịch văn bản sau:\n\n{text}"}
    ]

# --- HÀM GỌI CÁC ENGINE ---

# Cập nhật: Nhận thêm biến model_name
def call_gemini(text, style, model_name):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Sử dụng model_name được truyền vào từ dropdown
        model = genai.GenerativeModel(model_name)
        
        # Gemini không dùng cấu trúc chat list như OpenAI, nên nối prompt thủ công
        msgs = build_messages(text, style)
        full_prompt = msgs[0]['content'] + "\n\n" + msgs[1]['content']
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e: return f"❌ Lỗi Gemini ({model_name}): {e}"

def call_openai(text, style):
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=build_messages(text, style)
        )
        return response.choices[0].message.content
    except Exception as e: return f"❌ Lỗi OpenAI: {e}"

def call_ollama(text, style, model_name="qwen2.5:7b"):
    try:
        client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
        
        response = client.chat.completions.create(
            model=model_name,
            messages=build_messages(text, style),
            temperature=0.3, # Giảm nhiệt độ để AI bớt "sáng tạo" lung tung
            presence_penalty=1.1 
        )
        return response.choices[0].message.content
    except Exception as e: 
        return f"❌ Lỗi Ollama: Hãy đảm bảo bạn đã chạy 'ollama run {model_name}'. Chi tiết: {e}"

# --- GIAO DIỆN CHÍNH ---
st.title("📖 AI Light Novel Reader (V7 Stable)")

# Quản lý State
if 'url_input' not in st.session_state: st.session_state['url_input'] = ""
if 'translated_content' not in st.session_state: st.session_state['translated_content'] = ""
if 'auto_run' not in st.session_state: st.session_state['auto_run'] = False
if 'stats_info' not in st.session_state: st.session_state['stats_info'] = ""

# HÀM CALLBACK
def trigger_translation():
    st.session_state['auto_run'] = True

def handle_nav(step):
    current = st.session_state['url_input']
    if current:
        new_url = modify_chapter_number(current, step)
        if new_url != current:
            st.session_state['url_input'] = new_url
            st.session_state['auto_run'] = True
        else:
            st.toast("⚠️ Không tìm thấy số chương!", icon="🚫")

# 1. INPUT
st.text_input(
    "Link chương truyện:", 
    key="url_input", 
    placeholder="Nhập link chương 1...",
    on_change=trigger_translation
)

# 2. CONFIG
c1, c2 = st.columns(2)
with c1:
    # CẬP NHẬT DANH SÁCH MODEL MỚI TẠI ĐÂY
    model_options = [
        "Gemini (gemini-1.5-flash)", # Model ổn định cũ
        "Gemini (gemini-2.5-flash)",
        "Gemini (gemini-flash-latest)",
        "Gemini (gemini-flash-lite-latest)",
        "Gemini (gemini-3-flash-preview)",
        "Gemini (gemma-3-27b-it)",     # Gemma cũng dùng thư viện Google
        "Ollama (qwen2.5:7b)",
        "Ollama (qwen2.5:1.5b)",
        "ChatGPT (gpt-4o-mini)"
    ]
    
    model_choice = st.selectbox("Engine", model_options)

with c2:
    style_choice = st.selectbox(
        "Style", 
        ("Fantasy / Isekai", "Kiếm Hiệp / Tiên Hiệp", "Đời thường", "Sắc (R18)")
    )

# Nút Dịch
st.button("🚀 ĐỌC NGAY", on_click=trigger_translation, type="primary", use_container_width=True)

# 3. LOGIC XỬ LÝ (CHẠY NGẦM)
if st.session_state['auto_run'] and st.session_state['url_input']:
    url = st.session_state['url_input']
    
    with st.spinner(f"⏳ Đang tải và dịch: {url}..."):
        # Reset kết quả cũ
        st.session_state['translated_content'] = ""
        st.session_state['stats_info'] = ""
        
        # 1. Crawl
        raw_text = get_content(url)
        
        if raw_text:
            # 2. Dịch & Đo giờ
            start_time = time.time()
            
            # --- LOGIC GỌI MODEL MỚI ---
            if "Gemini" in model_choice:
                # Tách tên model từ chuỗi hiển thị. Ví dụ: "Gemini (gemini-2.5-flash)" -> "gemini-2.5-flash"
                gemini_model_id = model_choice.split("(")[1].replace(")", "")
                final_text = call_gemini(raw_text, style_choice, gemini_model_id)
                
            elif "ChatGPT" in model_choice:
                final_text = call_openai(raw_text, style_choice)
                
            else: # Ollama
                # Lấy tên model Ollama
                ollama_model = model_choice.split("(")[1].replace(")", "")
                final_text = call_ollama(raw_text, style_choice, ollama_model)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 3. Tính toán thống kê
            word_count = len(final_text.split())
            speed = word_count / duration if duration > 0 else 0
            
            # Lưu vào Session State
            st.session_state['translated_content'] = final_text
            st.session_state['stats_info'] = f"⏱️ Thời gian: {duration:.2f}s  |  ⚡ Tốc độ: {speed:.1f} từ/giây  |  📝 Số từ: {word_count}"
            
        else:
            st.error("❌ Lỗi: Không lấy được nội dung web! (Web chặn bot hoặc link sai)")
    
    # Tắt cờ chạy
    st.session_state['auto_run'] = False

# 4. HIỂN THỊ KẾT QUẢ
if st.session_state['translated_content']:
    st.divider()
    
    # Hiển thị thanh thông tin
    if st.session_state['stats_info']:
        st.markdown(f"""
        <div class="speed-box">
            {st.session_state['stats_info']}
        </div>
        """, unsafe_allow_html=True)
    
    # Hiển thị nội dung truyện
    st.markdown(f"""
    <div class="reading-content">
        {st.session_state['translated_content']}
    </div>
    """, unsafe_allow_html=True)
    
    # Thanh điều hướng
    st.write("")
    b1, b2 = st.columns(2)
    with b1: 
        st.button("⬅️ Chương trước", on_click=handle_nav, args=(-1,), use_container_width=True)
    with b2: 
        st.button("Chương tiếp theo ➡️", on_click=handle_nav, args=(1,), type="primary", use_container_width=True)
