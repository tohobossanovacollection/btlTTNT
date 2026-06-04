import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import get_connection
router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    fullname: str
    email: str
    username: str
    password: str
class EmailRequest(BaseModel):
    email: str

# Thông tin cấu hình Email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "nguyenho220704@gmail.com"  # Email của bạn
SENDER_PASSWORD = "nagr owvs yrfj toia"  # Mã 16 ký tự App Password

def send_email_otp(receiver_email, otp_code):
    try:
        # Tạo nội dung email
        msg = MIMEMultipart()
        msg['From'] = f"Galaxy AI Law Support <{SENDER_EMAIL}>"
        msg['To'] = receiver_email
        msg['Subject'] = f"Mã xác thực OTP: {otp_code}"

        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #0f0c29; color: white; padding: 20px;">
                <h2 style="color: #00d2ff;">Galaxy AI Law</h2>
                <p>Chào bạn,</p>
                <p>Bạn đã yêu cầu khôi phục mật khẩu. Mã OTP của bạn là:</p>
                <h1 style="background: #1a1a2e; padding: 10px; border: 1px solid #00d2ff; text-align: center; color: #92fe9d;">
                    {otp_code}
                </h1>
                <p>Mã này có hiệu lực trong vòng 5 phút. Vui lòng không chia sẻ mã này với bất kỳ ai.</p>
                <hr style="border: 0.5px solid #333;">
                <p style="font-size: 0.8rem; color: #aaa;">Đây là tin nhắn tự động, vui lòng không phản hồi.</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))

        # Kết nối và gửi
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Bảo mật kết nối
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Lỗi gửi email: {e}")
        return False
# ===============================
# Đăng nhập hệ thống
# ===============================
@router.post("/login")
def login(req: LoginRequest):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT 
                tk.MaTaiKhoan,
                nd.MaNguoiDung,
                nd.HoTen,
                vt.TenVaiTro,
                tk.TrangThai
            FROM TaiKhoan tk
            JOIN NguoiDung nd ON tk.MaNguoiDung = nd.MaNguoiDung
            JOIN VaiTro vt ON tk.MaVaiTro = vt.MaVaiTro
            WHERE tk.TenDangNhap = ? AND tk.MatKhau = ?
        """, req.username, req.password)

        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu")

        # 🔒 Kiểm tra tài khoản bị khóa
        if row[4] == "Đã khóa":
            raise HTTPException(
                status_code=403,
                detail="Tài khoản đã bị khóa"
            )

        return {
            "user_id": row[1],
            "name": row[2],
            "role": row[3]
        }

    finally:
        cursor.close()
        conn.close()

# ===============================
# Đăng ký tài khoản
# ===============================
@router.post("/register")
def register(req: RegisterRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Thêm vào bảng NguoiDung (OUTPUT INSERTED dùng cho SQL Server)
        cursor.execute("""
            INSERT INTO NguoiDung (HoTen, Email)
            OUTPUT INSERTED.MaNguoiDung
            VALUES (?, ?)
        """, req.fullname, req.email)
        
        user_id = cursor.fetchone()[0]

        # 2. Thêm vào bảng TaiKhoan (Mặc định vai trò USER là 2)
        cursor.execute("""
            INSERT INTO TaiKhoan (TenDangNhap, MatKhau, MaNguoiDung, MaVaiTro)
            VALUES (?, ?, ?, 2)
        """, req.username, req.password, user_id)

        conn.commit()
        return {"message": "Đăng ký thành công!"}
    except Exception as e:
        conn.rollback()
        # Lỗi thường xảy ra do Unique Constraint của Email hoặc TenDangNhap
        raise HTTPException(status_code=400, detail="Tên đăng nhập hoặc Email đã tồn tại!")
    finally:
        cursor.close()
        conn.close()
@router.post("/forgot-password")
def forgot_password(email: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Kiểm tra email
    cursor.execute("SELECT MaNguoiDung FROM NguoiDung WHERE Email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="Email không tồn tại")
    
    # 2. Tạo token ngẫu nhiên (Ví dụ đơn giản)
    import secrets
    token = secrets.token_hex(16)
    
    # 3. Lưu token vào DB (Cần thêm bảng hoặc cột ResetToken vào bảng TaiKhoan)
    cursor.execute("""
        UPDATE TaiKhoan SET ResetToken = ?, TokenExpiry = DATEADD(hour, 1, GETDATE())
        WHERE MaNguoiDung = ?
    """, (token, user[0]))
    
    conn.commit()
    conn.close()
    
    # 4. Gửi email chứa link: http://yourdomain.com/reset-password.html?token=...
    # (Sử dụng smtplib hoặc fastapi-mail)
    return {"message": "Vui lòng kiểm tra email để đặt lại mật khẩu"}
from pydantic import BaseModel

# 1. Định nghĩa cấu trúc dữ liệu gửi lên từ form đổi mật khẩu
class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    # 2. Kiểm tra mã OTP có khớp và còn hạn không
    cursor.execute("""
        SELECT MaNguoiDung FROM TaiKhoan 
        WHERE OTP_Code = ? AND OTP_Expiry > GETDATE()
        AND MaNguoiDung = (SELECT MaNguoiDung FROM NguoiDung WHERE Email = ?)
    """, (req.otp, req.email))
    
    res = cursor.fetchone()
    
    if res:
        # 3. Cập nhật mật khẩu mới và xóa mã OTP đã dùng
        cursor.execute("""
            UPDATE TaiKhoan 
            SET MatKhau = ?, OTP_Code = NULL, OTP_Expiry = NULL 
            WHERE MaNguoiDung = ?
        """, (req.new_password, res[0]))
        conn.commit()
        conn.close()
        return {"message": "Đặt lại mật khẩu thành công"}
    
    conn.close()
    raise HTTPException(status_code=400, detail="Mã OTP không đúng hoặc đã hết hạn!")
@router.post("/find-account")
def find_account(req: EmailRequest):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MaNguoiDung, HoTen, Email FROM NguoiDung WHERE Email = ?", (req.email,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản!")
    return {"id": user[0], "name": user[1], "email": user[2]}
import random

@router.post("/send-otp")
def send_otp(req: EmailRequest):
    otp = str(random.randint(100000, 999999))
    
    # 1. Lưu OTP vào Database (SQL Server)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Cập nhật mã OTP và thời gian hết hạn (5 phút sau)
        cursor.execute("""
            UPDATE TaiKhoan 
            SET OTP_Code = ?, OTP_Expiry = DATEADD(minute, 5, GETDATE())
            WHERE MaNguoiDung = (SELECT MaNguoiDung FROM NguoiDung WHERE Email = ?)
        """, (otp, req.email))
        conn.commit()
    finally:
        conn.close()

    # 2. Gửi Email thực tế
    success = send_email_otp(req.email, otp)
    
    if success:
        return {"message": "OTP đã được gửi thành công"}
    else:
        raise HTTPException(status_code=500, detail="Không thể gửi email lúc này")
@router.post("/verify-otp")
def verify_otp(email: str, otp: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MaNguoiDung FROM TaiKhoan 
        WHERE OTP_Code = ? AND OTP_Expiry > GETDATE()
        AND MaNguoiDung = (SELECT MaNguoiDung FROM NguoiDung WHERE Email = ?)
    """, (otp, email))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Mã OTP không đúng hoặc đã hết hạn")
@router.get("/profile/{user_id}")
def get_user_profile(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Truy vấn kết hợp giữa bảng NguoiDung (Họ tên, Email) và TaiKhoan (Tên đăng nhập)
        query = """
            SELECT n.HoTen, n.Email, t.TenDangNhap 
            FROM NguoiDung n
            JOIN TaiKhoan t ON n.MaNguoiDung = t.MaNguoiDung
            WHERE n.MaNguoiDung = ?
        """
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()

        if row:
            return {
                "full_name": row[0],
                "email": row[1],
                "username": row[2]
            }
        else:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    except Exception as e:
        print(f"Lỗi Profile: {e}")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lấy hồ sơ")
    finally:
        conn.close()