# RAG TaxBot

Demo chatbot tu van thue su dung Streamlit va pipeline RAG noi bo.

- App Streamlit: `streamlit_app/app.py`
- Pipeline RAG: `backend/app/services`
- FastAPI backend: `backend/main.py` (tuy chon, chi dung de debug API)
- Du lieu truy xuat: cac file Markdown trong `data/processed`
- Embedding retrieval: local/offline hash TF-IDF, khong goi API ngoai
- LLM: Gemini API
- Lich su tro chuyen: SQLite local trong `storage/chat_history.sqlite3`

## Yeu Cau

- Windows + PowerShell
- Python 3.10 tro len
- Gemini API key trong Google AI Studio

## 1. Cau Hinh Gemini

Vao thu muc `backend` va tao file `.env`:

```powershell
cd backend
Copy-Item .env.example .env
```

Mo `backend/.env` va dien API key:

```env
APP_NAME="FastAPI Tax Chatbot"
DEBUG=True
PORT=8000

GOOGLE_API_KEY="dien_gemini_api_key_cua_ban_vao_day"
MODEL_NAME="gemini-2.5-flash-lite"
LOCAL_EMBEDDING_DIM=2048
LOCAL_EMBEDDING_MIN_TOKEN_LENGTH=2
```

## 2. Cai Thu Vien

Tu thu muc goc project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
pip install -r streamlit_app\requirements.txt
```

Neu PowerShell chan activate script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 3. Chay Streamlit

Tu terminal da activate `.venv`:

```powershell
python -m streamlit run streamlit_app\app.py
```

Mo:

```text
http://localhost:8501
```

Streamlit goi truc tiep pipeline Python trong `backend/app/services`, khong can mo backend rieng o cong `8000`.

## 4. FastAPI Debug Tuy Chon

Chi can buoc nay neu muon test API bang Swagger.

```powershell
cd backend
python main.py
```

Mo:

```text
http://127.0.0.1:8000/docs
```

## Luong Xu Ly

1. Streamlit nhan cau hoi.
2. Streamlit goi `handle_chat()` trong pipeline Python.
3. Pipeline doc cac file `.md` trong `data/processed`.
4. He thong tao/tai embedding local va tim cac doan luat lien quan.
5. Intent router chon `standard_rag` hoac `rat_lite`.
6. Self-RAG danh gia do lien quan, do ho tro va do huu ich cua cau tra loi.
7. Gemini tong hop cau tra loi.
8. Streamlit hien thi cau tra loi, can cu phap ly ngan gon, do tin cay va runtime debug.
9. Streamlit tu dong luu lich su vao SQLite local.

## Loi Thuong Gap

### Khong mo duoc Streamlit o cong 8501

Chay voi cong khac:

```powershell
python -m streamlit run streamlit_app\app.py --server.port 8502
```

### Gemini chua cau hinh

Kiem tra `backend/.env` co:

```env
GOOGLE_API_KEY="api_key_cua_ban"
```

Sau khi sua `.env`, restart Streamlit.

### Loi `429 RESOURCE_EXHAUSTED`

Gemini API key da het quota hoac model khong con quota free. Thu:

```env
MODEL_NAME="gemini-2.5-flash-lite"
```

Hoac doi API key/bat billing.

### Loi `models/gemini-1.5-flash is not found`

Dung model moi hon trong `backend/.env`:

```env
MODEL_NAME="gemini-2.5-flash-lite"
```

### Lan dau hoi bi cham

Lan dau pipeline se tai cache embedding va tao vector cho kho luat neu can.

## Cau Truc Thu Muc

```text
btlTTNT/
  streamlit_app/
    app.py
    chat_store.py
    requirements.txt
  backend/
    main.py
    requirements.txt
    .env.example
    app/
      api/
      services/
      utils/
  data/
    processed/
    raw/
      luat/
      nghi_dinh/
      thong_tu/
  scripts/
    convert_raw_to_md.py
  storage/
    chat_history.sqlite3
```
