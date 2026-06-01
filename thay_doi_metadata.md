# Hướng Dẫn: Cấu Trúc Metadata & Tiền Xử Lý Văn Bản Pháp Luật Sửa Đổi

Tài liệu này tổng hợp các phương pháp tiền xử lý và cấu trúc Metadata giúp Chatbot AI (RAG) luôn tìm được đúng văn bản hợp nhất hoặc các nghị định sửa đổi mới nhất đối với các điều luật đã thay đổi.

---

## 1. TẦM QUAN TRỌNG CỦA METADATA
Trong lĩnh vực pháp luật, nội dung văn bản (Text) là chưa đủ. Hệ thống cần hiểu được **ngữ cảnh pháp lý** của văn bản đó (văn bản còn hiệu lực không? ai sửa đổi nó? nó thuộc cấp bậc nào?). Metadata chính là "thẻ căn cước" giúp bộ máy truy xuất (Retriever) thực hiện việc lọc và ưu tiên dữ liệu một cách thông minh.

---

## 2. CẤU TRÚC METADATA CHI TIẾT CHO MỖI CHUNK

Mỗi đoạn văn bản (chunk) sau khi chia nhỏ cần được gắn bộ Metadata sau:

### A. Nhóm Định danh & Cấp bậc (Identity)
- `doc_number`: Số hiệu văn bản (Ví dụ: `38/2019/QH14`).
- `legal_hierarchy`: Cấp bậc pháp lý (`Luật`, `Nghị định`, `Thông tư`). Giúp ưu tiên văn bản có giá trị pháp lý cao hơn.
- `is_consolidated`: Boolean (`true/false`). Đánh dấu văn bản hợp nhất để ưu tiên truy xuất.

### B. Nhóm Hiệu lực & Thời gian (Validity)
- `effective_date`: Ngày văn bản bắt đầu có hiệu lực.
- `expiry_date`: Ngày văn bản hết hiệu lực (nếu có).
- `status`: Trạng thái văn bản (`active` - còn hiệu lực, `expired` - hết hiệu lực, `partially_amended` - bị sửa đổi một phần).

### C. Nhóm Mối quan hệ & Sửa đổi (Relationships)
- `amends_doc`: ID hoặc số hiệu của văn bản gốc bị sửa đổi.
- `amends_article`: Số Điều/Khoản cụ thể mà chunk này sửa đổi/thay thế.
- `version`: Phiên bản của nội dung (`latest` cho phiên bản mới nhất).

---

## 3. QUY TRÌNH TIỀN XỬ LÝ (PREPROCESSING PIPELINE)

Để chatbot luôn tìm đúng văn bản mới nhất, quy trình tiền xử lý cần thực hiện 5 bước:

1.  **Legal-Structure Chunking**: Chia nhỏ văn bản theo cấu trúc `Điều > Khoản > Điểm`. Không chia theo số ký tự để tránh mất ngữ cảnh.
2.  **Metadata Enrichment**: Trích xuất thủ công hoặc tự động các thông tin hiệu lực và mối quan hệ sửa đổi từ văn bản.
3.  **Link-Back Mapping**: Tạo liên kết hai chiều. Đoạn sửa đổi trỏ đến đoạn gốc, và đoạn gốc được đánh dấu nhãn "Đã bị sửa đổi bởi...".
4.  **Priority Indexing**: Gán trọng số cao hơn cho các chunk thuộc **Văn bản hợp nhất** trong cơ sở dữ liệu vector.
5.  **Status Tagging**: Thường xuyên cập nhật trạng thái `status` cho các văn bản cũ khi có văn bản mới ban hành thay thế.

---

## 4. CƠ CHẾ TRUY XUẤT THÔNG MINH (RETRIEVAL LOGIC)

Hệ thống RAG sẽ sử dụng Metadata theo các bước sau để đảm bảo độ chính xác:

1.  **Bước 1 - Filtering**: Loại bỏ tất cả các chunk có `status: expired`. Lọc theo `effective_date` dựa trên thời gian trong câu hỏi của người dùng.
2.  **Bước 2 - Vector Search**: Tìm các đoạn có nội dung tương đồng nhất.
3.  **Bước 3 - Relationship Checking**: Nếu tìm thấy cả đoạn gốc và đoạn sửa đổi, hệ thống dựa vào `amends_doc` và `version: latest` để chọn đoạn mới nhất.
4.  **Bước 4 - Reranking**: Đẩy các đoạn từ **Văn bản hợp nhất** lên vị trí ưu tiên số 1 để LLM đọc trước.
5.  **Bước 5 - Prompt Construction**: AI tổng hợp câu trả lời và ghi rõ: *"Điều này ban đầu quy định tại X, nhưng hiện đã được sửa đổi bởi Nghị định Y (có hiệu lực từ ngày Z)..."*.

---

## 5. VÍ DỤ CẤU TRÚC JSON METADATA

```json
{
  "chunk_id": "nd_126_2020_dieu_8_khoan_1_sua_doi",
  "content": "Các loại thuế khai theo tháng, khai theo quý...",
  "metadata": {
    "doc_number": "126/2020/NĐ-CP",
    "is_consolidated": false,
    "effective_date": "2020-12-05",
    "status": "active",
    "amends_doc": "38/2019/QH14",
    "amends_article": "Điều 55",
    "version": "latest",
    "legal_hierarchy": "Nghị định",
    "tax_domain": "Quản lý thuế"
  }
}
```

---
*Tài liệu này được soạn thảo để tối ưu hóa khả năng truy xuất của AI Chatbot tư vấn pháp luật.*
