# RAG TaxBot

Demo chatbot tu van thue su dung Streamlit va pipeline RAG noi bo.

- App Streamlit: `streamlit_app/app.py`
- Pipeline RAG: `backend/app/services`
- FastAPI backend: `backend/main.py` (tuy chon, chi dung de debug API)
- Du lieu truy xuat: cac file Markdown trong `data/processed`
- Embedding retrieval: local/offline hash TF-IDF, khong goi API ngoai
- LLM: Groq API
- Lich su tro chuyen: SQLite local trong `storage/chat_history.sqlite3`

## Yeu Cau

- Windows + PowerShell
- Python 3.10 tro len
- Groq API key

## 1. Cau Hinh Groq

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

GROQ_API_KEY="dien_groq_api_key_cua_ban_vao_day"
GROQ_MODEL_NAME="llama-3.3-70b-versatile"
RAGAS_GROQ_MODEL_NAME="llama-3.3-70b-versatile"
LOCAL_EMBEDDING_DIM=2048
LOCAL_EMBEDDING_MIN_TOKEN_LENGTH=2
```

## 2. Cai Thu Vien

Tu thu muc goc project:

```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r streamlit_app/requirements.txt
```

Neu PowerShell chan activate script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 3. Chay Streamlit

Tu terminal da activate `.venv`:

```powershell
python -m streamlit run streamlit_app/app.py
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
7. Groq tong hop cau tra loi.
8. Streamlit hien thi cau tra loi, can cu phap ly ngan gon, do tin cay va runtime debug.
9. Streamlit tu dong luu lich su vao SQLite local.

## Loi Thuong Gap

### Groq chua cau hinh

Kiem tra `backend/.env` co:

```env
GROQ_API_KEY="api_key_cua_ban"
```

Sau khi sua `.env`, restart Streamlit.

### Loi `429` hoac rate limit

Groq API key co the da het quota hoac gui qua nhieu request trong thoi gian ngan. Thu giam tan suat goi, doi model hoac doi API key.

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
