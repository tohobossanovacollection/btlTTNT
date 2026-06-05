
# Giả lập một Database bằng Python Dictionary
# Cấu trúc lưu trữ: { user_id: [ {"role": "user", "text": "..."}, {"role": "model", "text": "..."} ] }
MOCK_CHAT_DB = {}

def get_all_users():
    # Trả về danh sách user_id đang hoạt động trong hệ thống giả lập
    return list(MOCK_CHAT_DB.keys())

def save_chat_to_db(user_id: int, role: str, text: str, session_id: str = None):
    """
    Lưu một lượt thoại (của user hoặc của bot) vào DB giả lập.
    Đã đồng bộ lại tham số (role, text) khớp với logic gọi hàm ở chat.py tối ưu.
    """
    if not user_id:
        return None
        
    # Nếu user này chưa từng chat, khởi tạo một danh sách rỗng
    if user_id not in MOCK_CHAT_DB:
        MOCK_CHAT_DB[user_id] = []
        
    # Thêm tin nhắn mới vào lịch sử của user
    MOCK_CHAT_DB[user_id].append({
        "role": role,
        "text": text,
        "session_id": session_id
    })
    
    print(f"💾 [Mock DB] Đã lưu tin nhắn từ ({role}) cho User ID: {user_id}")
    return True

def get_history_from_db(user_id: int):
    """
    Lấy toàn bộ lịch sử chat của một user để nạp vào Context cho Gemini 
    hoặc trả về cho giao diện Frontend hiển thị.
    """
    if not user_id:
        return []
        
    # Trả về danh sách tin nhắn cũ, nếu user mới toanh thì trả về mảng rỗng []
    return MOCK_CHAT_DB.get(user_id, [])