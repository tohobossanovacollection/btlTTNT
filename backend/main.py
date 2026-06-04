import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    # Lấy cổng từ .env hoặc mặc định là 8000
    port = int(os.getenv("PORT", 8000))
    # Chạy ứng dụng 'app' nằm trong gói 'app.main'
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)