# RAG TaxBot

Demo chatbot tu van thue su dung RAG bang mot app Streamlit duy nhat:

- App Streamlit: `streamlit_app/app.py`
- Pipeline RAG noi bo: `backend/app/services`
- FastAPI backend: `backend/main.py` (tuy chon, chi dung de debug API)
- Frontend tinh cu: `index.html`, `assets/app.js`, `assets/styles.css` (legacy)
- Retrieval: doc/markdown trong `data/processed`
- Retrieval embedding: local/offline hash TF-IDF (khong goi API ngoai)
- LLM: Gemini API
- Lich su tro chuyen: SQLite local trong `storage/chat_history.sqlite3`

## Yeu cau

- Windows + PowerShell
- Python 3.10 tro len
- Gemini API key trong Google AI Studio

## 1. Tao file cau hinh Gemini

Vao thu muc backend:

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

Ghi chu:

- Khong commit file `.env` len Git.
- Gemini API key chi dung cho buoc tao cau tra loi, khong dung de tao embeddings retrieval.
- Neu gap loi `429 RESOURCE_EXHAUSTED`, nghia la key/model hien tai da het quota o buoc sinh cau tra loi. Retrieval van chay local/offline.

## 2. Cai thu vien Python

Tu thu muc goc project:

```powershell
cd ..
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
pip install -r streamlit_app\requirements.txt
```

Neu PowerShell chan activate script, chay:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Sau do mo terminal moi va activate lai:

```powershell
cd ..
.\.venv\Scripts\Activate.ps1
```

## 3. Chay app Streamlit duy nhat

Tu terminal da activate `.venv`:

```powershell
python -m streamlit run streamlit_app\app.py
```

Mo trinh duyet:

```text
http://localhost:8501
```

Streamlit se goi truc tiep pipeline Python trong `backend/app/services`, khong can mo backend rieng o cong `8000`.
Lich su tro chuyen duoc luu local vao `storage/chat_history.sqlite3`; file nay da duoc ignore khoi Git.

## 4. Chay FastAPI de debug (tuy chon)

Chi can buoc nay neu muon test API bang Swagger hoac frontend tinh cu.

```powershell
cd backend
python main.py
```

```text
http://127.0.0.1:8000/docs
```

## 4b. Chay frontend tinh cu (legacy, tuy chon)

Khong can dung buoc nay khi chay app Streamlit duy nhat.

Mo them mot terminal PowerShell moi, tu thu muc goc project:

```powershell
cd ..
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

## 5. Test API bang Swagger (tuy chon)

Khong can buoc nay khi dung app Streamlit duy nhat.

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
  "question": "Luong 10 trieu mot thang co phai nop thue TNCN khong?",
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

1. Streamlit nhan cau hoi tu nguoi dung.
2. Streamlit goi truc tiep `handle_chat()` trong pipeline Python.
3. Pipeline doc cac file `.md` trong `data/processed`.
4. Pipeline tao/tai embedding local va tim cac doan luat lien quan.
5. Intent router chon `standard_rag` hoac `rat_lite`.
6. CRAG danh gia do tin cay cua nguon.
7. He thong tong hop cau tra loi bang Gemini.
8. Streamlit hien thi cau tra loi, nguon, score va runtime meta.
9. Streamlit luu cau hoi va cau tra loi vao lich su tro chuyen local.

## 7. Cac loi thuong gap

### Khong mo duoc Streamlit o cong 8501

Chay Streamlit voi cong khac:

```powershell
python -m streamlit run streamlit_app\app.py --server.port 8502
```

### Gemini chua cau hinh

Kiem tra `backend/.env` co dong:

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

Model `gemini-1.5-flash` khong kha dung voi SDK/API hien tai. Dung:

```env
MODEL_NAME="gemini-2.5-flash-lite"
```

### Lan dau hoi bi cham

Lan dau pipeline se tai cache embedding va tao vector cho kho luat neu can. Cho vai chuc giay den vai phut tuy may.

## 8. Dung app

Dung Streamlit: bam `Ctrl+C` trong terminal dang chay Streamlit.

Neu co chay frontend tinh cu:

```powershell
.\scripts\stop-live-server.ps1
```

Neu chay frontend o cong khac va script khong dung duoc, dong terminal PowerShell dang chay frontend.

## Cau truc thu muc

```text
btlTTNT/
  index.html
  streamlit_app/
    app.py
    chat_store.py
    requirements.txt
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
