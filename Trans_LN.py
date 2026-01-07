import google.generativeai as genai
import time
from concurrent.futures import ThreadPoolExecutor

# --- CẤU HÌNH ---
raw_api_key = "AIzaSyAOoQe-jpoOTCwLAmj9lbf7LHuPEhr7gu8"
API_KEY = raw_api_key.strip()
genai.configure(api_key=API_KEY)

# Danh sách tất cả model từ log của bạn
ALL_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite-001",
    "gemini-2.0-flash-lite",
    "gemini-exp-1206",
    "gemini-flash-latest",     # Khuyên dùng
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
    "gemini-3-flash-preview",  # Thử vận may
    "gemini-3-pro-preview",
    "nano-banana-pro-preview",
    "gemma-3-27b-it",
]

print(f"--- BẮT ĐẦU KIỂM TRA {len(ALL_MODELS)} MODEL ---\n")
print(f"{'MODEL NAME':<35} | {'TRẠNG THÁI':<15} | {'CHI TIẾT'}")
print("-" * 80)

def check_quota(model_name):
    try:
        # Gửi 1 từ "Hi" cực ngắn để test
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hi")
        
        # Nếu chạy xuống đây tức là thành công
        return model_name, "✅ OK", "Dùng ngon (Limit > 0)"
        
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "Quota exceeded" in error_str:
            return model_name, "❌ FULL", "Hết lượt / Limit = 0"
        elif "404" in error_str or "not found" in error_str.lower():
            return model_name, "⚠️ 404", "Không tìm thấy model"
        else:
            # Lấy dòng lỗi ngắn gọn
            short_err = error_str.split('\n')[0][:30] + "..."
            return model_name, "🚫 LỖI", short_err

# Chạy đa luồng (5 model cùng lúc) để nhanh hơn
results = []
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(check_quota, name) for name in ALL_MODELS]
    for future in futures:
        name, status, detail = future.result()
        print(f"{name:<35} | {status:<15} | {detail}")
        if status == "✅ OK":
            results.append(name)

print("-" * 80)
print("\n🎉 KẾT QUẢ: CÁC MODEL BẠN CÓ THỂ DÙNG NGAY BÂY GIỜ:")
if results:
    for r in results:
        print(f"   👉 {r}")
else:
    print("   ❌ Không có model nào khả dụng. Tài khoản của bạn có thể bị khóa Free Tier toàn bộ.")