import streamlit as st
import toml

# In ra toàn bộ các key mà Streamlit đọc được
print("------------------------------------------------")
print("🔑 DANH SÁCH KEY ĐANG CÓ TRONG SECRETS:")
try:
    # Hack nhẹ để in ra keys, chuyển về dạng list để dễ nhìn
    print(list(st.secrets.keys()))
except Exception as e:
    print(f"❌ Không đọc được secrets nào cả! Lỗi: {e}")
print("------------------------------------------------")