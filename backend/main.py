import uvicorn
import os
from dotenv import load_dotenv

#load_dotenv()
load_dotenv(dotenv_path=".env")
if __name__ == "__main__":
    # Lấy cổng từ .env hoặc mặc định là 8000
    port = int(os.getenv("PORT", 8000))
    # Chạy ứng dụng 'app' nằm trong gói 'app.main'
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)



# TEST backend độc lập với frontend 
# Chạy Swagger ở http://127.0.0.1:8000/docs#/Chat/chat_api_v1_chat__post
