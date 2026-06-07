# RAG TaxBot

Demo chatbot tu van thue su dung RAG:

- Frontend tinh: `index.html`, `assets/app.js`, `assets/styles.css`
- Backend: FastAPI
- Retrieval: doc/markdown trong `data/processed`
- Embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- LLM: Gemini API

## Yeu cau

- Windows + PowerShell
- Python 3.10 tro len
- Internet trong lan chay dau de tai model embedding tu Hugging Face
- Gemini API key trong Google AI Studio

## 1. Tao file cau hinh backend

Vao thu muc backend:

```powershell
cd D:\Vscode\btlTTNT\backend
Copy-Item .env.example .env
```

Mo `backend/.env` va dien API key:

```env
APP_NAME="FastAPI Tax Chatbot"
DEBUG=True
PORT=8000

GOOGLE_API_KEY="dien_gemini_api_key_cua_ban_vao_day"
MODEL_NAME="gemini-2.5-flash-lite"

SECRET_KEY="your-super-secret-key"
```

Ghi chu:

- Khong commit file `.env` len Git.
- Free API key dung duoc cho demo, nhung co quota gioi han.
- Neu gap loi `429 RESOURCE_EXHAUSTED`, nghia la key/model hien tai da het quota. Co the cho quota reset, doi API key, doi model lite khac, hoac bat billing.

## 2. Cai thu vien Python

Tu thu muc `backend`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Neu PowerShell chan activate script, chay:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Sau do mo terminal moi va activate lai:

```powershell
cd D:\Vscode\btlTTNT\backend
.\.venv\Scripts\Activate.ps1
```

## 3. Chay backend FastAPI

Tu thu muc `backend`:

```powershell
python main.py
```

Backend se chay o:

```text
http://127.0.0.1:8000
```

Swagger UI de test API:

```text
http://127.0.0.1:8000/docs
```

Lan goi chat dau tien co the lau vi backend can tao embedding cho cac van ban luat. Cac lan sau se nhanh hon.

## 4. Chay frontend

Mo them mot terminal PowerShell moi, tu thu muc goc project:

```powershell
cd D:\Vscode\btlTTNT
.\scripts\start-live-server.ps1 -Port 5501
```

Mo trinh duyet:

```text
http://127.0.0.1:5501
```

Ly do dung `5501`: tren mot so may, cong `5500` co the da bi tien trinh khac chiem. Neu may ban ranh cong `5500`, co the chay:

```powershell
.\scripts\start-live-server.ps1
```

va mo:

```text
http://127.0.0.1:5500
```

## 5. Test API bang Swagger

Mo:

```text
http://127.0.0.1:8000/docs
```

Chon:

```text
POST /api/v1/chat/
```

Bam `Try it out`, nhap body:

```json
{
  "question": "Lương 10 triệu một tháng có phải nộp thuế TNCN không?",
  "user_id": 1,
  "session_id": 1
}
```

Bam `Execute`.

Ket qua dung se co dang:

```json
{
  "answer": "...",
  "sources": ["..."],
  "chat_id": "sample-session-id"
}
```

## 6. Luong chay cua ung dung

1. Frontend gui cau hoi den `http://127.0.0.1:8000/api/v1/chat/`.
2. Backend doc cac file `.md` trong `data/processed`.
3. Backend tao embedding va tim cac doan luat lien quan.
4. Backend gui cau hoi + can cu phap ly sang Gemini.
5. Gemini tra loi dua tren context RAG.
6. Frontend hien thi cau tra loi va nguon truy xuat.

## 7. Cac loi thuong gap

### Khong mo duoc frontend o cong 5500

Chay frontend voi cong khac:

```powershell
.\scripts\start-live-server.ps1 -Port 5501
```

### Backend bao thieu `GOOGLE_API_KEY`

Kiem tra `backend/.env` co dong:

```env
GOOGLE_API_KEY="api_key_cua_ban"
```

Sau khi sua `.env`, restart backend.

### Loi `429 RESOURCE_EXHAUSTED`

Gemini API key da het quota hoac model khong con quota free. Thu:

```env
MODEL_NAME="gemini-2.5-flash-lite"
```

Hoac doi API key/bat billing.

### Loi `models/gemini-1.5-flash is not found`

Model `gemini-1.5-flash` khong kha dung voi SDK/API hien tai. Dung:

```env
MODEL_NAME="gemini-2.5-flash-lite"
```

### Lan dau hoi bi cham

Lan dau backend se tai/load model embedding va tao vector cho kho luat. Cho vai chuc giay den vai phut tuy may va mang.

## 8. Dung server

Dung backend: bam `Ctrl+C` trong terminal dang chay backend.

Dung frontend:

```powershell
.\scripts\stop-live-server.ps1
```

Neu chay frontend o cong khac va script khong dung duoc, dong terminal PowerShell dang chay frontend.

## Cau truc thu muc

```text
btlTTNT/
  index.html
  assets/
    app.js
    styles.css
  backend/
    main.py
    requirements.txt
    .env.example
    app/
      api/
      services/
      prompts/
  data/
    processed/
    raw/
  scripts/
    start-live-server.ps1
    stop-live-server.ps1
```
