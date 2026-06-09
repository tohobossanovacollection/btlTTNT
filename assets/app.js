(function () {
  var STORAGE_KEY = "rag-taxbot-conversations";
  var DEFAULT_TITLE = "Cuộc trò chuyện mới";
  var API_BASE_URL = window.RAG_API_BASE_URL || "http://127.0.0.1:8000";
  var CHAT_API_URL = API_BASE_URL.replace(/\/$/, "") + "/api/v1/chat/";

  var state = {
    activeId: "",
    conversations: [],
    isSubmitting: false,
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function makeId() {
    return "chat_" + new Date().getTime() + "_" + Math.floor(Math.random() * 1000000);
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function safeReadStorage() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  function safeWriteStorage() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.conversations));
      byId("saveStatus").textContent = "Đã lưu";
    } catch (error) {
      byId("saveStatus").textContent = "Không lưu được";
    }
  }

  function welcomeMessage() {
    return {
      role: "bot",
      html:
        "<h2>Xin chào, tôi là demo RAG TaxBot.</h2>" +
        "<p>Nhập câu hỏi về thuế cho cá nhân, hộ kinh doanh, tổ chức, hóa đơn, kê khai, nộp thuế hoặc xử phạt. Cuộc trò chuyện sẽ được lưu lại trên trình duyệt local.</p>",
      warning: false,
    };
  }

  function normalizeConversation(item) {
    if (!item || !Array.isArray(item.messages)) return null;

    return {
      id: item.id || makeId(),
      title: item.title || DEFAULT_TITLE,
      createdAt: item.createdAt || nowIso(),
      updatedAt: item.updatedAt || nowIso(),
      audit: item.audit || { status: "waiting_for_question" },
      messages: item.messages.length ? item.messages : [welcomeMessage()],
    };
  }

  function createConversation() {
    var conversation = {
      id: makeId(),
      title: DEFAULT_TITLE,
      createdAt: nowIso(),
      updatedAt: nowIso(),
      audit: { status: "waiting_for_question" },
      messages: [welcomeMessage()],
    };

    state.conversations.unshift(conversation);
    state.activeId = conversation.id;
    safeWriteStorage();
    return conversation;
  }

  function getActiveConversation() {
    var i;

    for (i = 0; i < state.conversations.length; i += 1) {
      if (state.conversations[i].id === state.activeId) {
        return state.conversations[i];
      }
    }

    return createConversation();
  }

  function detectDomain(question) {
    var filter = byId("domainFilter").value;
    var text = question.toLowerCase();

    if (filter !== "auto") return filter;
    if (text.indexOf("không xuất hóa đơn") >= 0 || text.indexOf("trốn thuế") >= 0) return "invoice";
    if (text.indexOf("lương") >= 0 || text.indexOf("tiền lương") >= 0 || text.indexOf("tiền công") >= 0) return "tncn";
    if (text.indexOf("thu nhập cá nhân") >= 0 || text.indexOf("tncn") >= 0) return "tncn";
    if (text.indexOf("gtgt") >= 0 || text.indexOf("giá trị gia tăng") >= 0) return "gtgt";
    if (text.indexOf("chậm nộp") >= 0 || text.indexOf("xử phạt") >= 0) return "penalty";
    if (text.indexOf("tháng") >= 0 || text.indexOf("quý") >= 0 || text.indexOf("khai thuế") >= 0) return "qlt";
    if (text.indexOf("tndn") >= 0 || text.indexOf("miễn thuế") >= 0 || text.indexOf("phần mềm") >= 0) return "tndn";
    if (text.indexOf("hóa đơn") >= 0 || text.indexOf("chứng từ") >= 0) return "invoice";
    return "default";
  }

  function isRiskQuestion(question) {
    if (!byId("guardrailMode").checked) return false;

    var text = question.toLowerCase();
    return (
      text.indexOf("trốn thuế") >= 0 ||
      text.indexOf("giấu doanh thu") >= 0 ||
      text.indexOf("không xuất hóa đơn") >= 0 ||
      text.indexOf("không bị phát hiện") >= 0 ||
      text.indexOf("hóa đơn khống") >= 0 ||
      text.indexOf("chi phí giả") >= 0 ||
      text.indexOf("mua hóa đơn") >= 0
    );
  }

  function answerFor(question) {
    var domain = detectDomain(question);
    var risk = isRiskQuestion(question);
    var salaryAmount = extractMillionAmount(question);

    if (risk) {
      return {
        domain: "invoice",
        intent: "prohibited_request",
        risk: "PROHIBITED",
        title: "Tôi không thể hướng dẫn hành vi vi phạm quy định thuế.",
        body:
          "Tôi có thể hỗ trợ tra cứu quy định về xuất hóa đơn, kê khai đúng và rủi ro xử phạt khi không tuân thủ.",
        citations: ["Nghị định 123/2020/NĐ-CP về hóa đơn, chứng từ", "Nghị định 125/2020/NĐ-CP về xử phạt thuế và hóa đơn"],
        warning: true,
      };
    }

    if (domain === "tncn") {
      if (salaryAmount > 0 && salaryAmount <= 15.5) {
        return {
          domain: domain,
          intent: "salary_tax_check",
          risk: "MEDIUM",
          title: "Nếu chỉ có lương 10 triệu/tháng thì thường chưa phải nộp thuế TNCN.",
          body:
            "Theo dữ liệu hiện có, mức giảm trừ đối với bản thân người nộp thuế là 15,5 triệu đồng/tháng. Nếu bạn là cá nhân cư trú, chỉ có thu nhập tiền lương khoảng " +
            salaryAmount +
            " triệu đồng/tháng và không có thu nhập chịu thuế khác, thì mức này thấp hơn giảm trừ bản thân nên thường chưa phát sinh thuế thu nhập cá nhân. Cần kiểm tra thêm các yếu tố như bảo hiểm bắt buộc, người phụ thuộc, tình trạng cư trú và các khoản thu nhập khác trước khi kết luận chính thức.",
          citations: [
            "Luật Thuế thu nhập cá nhân, Điều 8: thuế TNCN đối với thu nhập từ tiền lương, tiền công được xác định trên thu nhập tính thuế.",
            "Luật Thuế thu nhập cá nhân, Điều 10: mức giảm trừ đối với người nộp thuế là 15,5 triệu đồng/tháng; mỗi người phụ thuộc là 6,2 triệu đồng/tháng.",
          ],
          warning: false,
        };
      }

      return {
        domain: domain,
        intent: "salary_tax_check",
        risk: "MEDIUM",
        title: "Cần tính thu nhập tính thuế trước khi kết luận thuế TNCN.",
        body:
          "Thuế TNCN từ tiền lương không chỉ dựa vào số lương gộp. Cần xác định tổng thu nhập chịu thuế, trừ bảo hiểm bắt buộc, giảm trừ bản thân, giảm trừ người phụ thuộc và các khoản giảm trừ khác nếu có. Sau đó mới áp dụng biểu thuế lũy tiến từng phần.",
        citations: [
          "Luật Thuế thu nhập cá nhân, Điều 8: thu nhập tính thuế từ tiền lương, tiền công.",
          "Luật Thuế thu nhập cá nhân, Điều 10: giảm trừ gia cảnh.",
        ],
        warning: false,
      };
    }

    if (domain === "gtgt") {
      return {
        domain: domain,
        intent: "concept_lookup",
        risk: "LOW",
        title: "Thuế GTGT là thuế tính trên phần giá trị tăng thêm.",
        body:
          "Trong demo này, câu trả lời được mô phỏng từ luồng RAG. Khi nối backend thật, hệ thống sẽ truy xuất điều khoản liên quan, kiểm tra hiệu lực văn bản và chỉ trả lời dựa trên context đã tìm được.",
        citations: ["Luật Thuế giá trị gia tăng số 48/2024/QH15", "Nghị định 181/2025/NĐ-CP"],
        warning: false,
      };
    }

    if (domain === "qlt") {
      return {
        domain: domain,
        intent: "business_case",
        risk: "MEDIUM",
        title: "Chưa đủ dữ kiện để kết luận khai theo tháng hay theo quý.",
        body:
          "Cần biết loại người nộp thuế, doanh thu hoặc thu nhập liên quan, loại thuế đang hỏi và thời điểm áp dụng. Hệ thống không nên kết luận chắc chắn khi thiếu các dữ kiện này.",
        citations: ["Thông tư 80/2021/TT-BTC", "Luật Quản lý thuế"],
        warning: false,
      };
    }

    if (domain === "penalty") {
      return {
        domain: domain,
        intent: "calculation_required",
        risk: "HIGH",
        title: "Kết quả tính minh họa: 600.000 đồng.",
        body:
          "Công thức minh họa: 100.000.000 x 0,03% x 20 ngày = 600.000 đồng. Khi triển khai thật, phần tính toán phải gọi calculator/rule engine và kiểm tra tỷ lệ áp dụng theo thời điểm hỏi.",
        citations: ["Luật Quản lý thuế", "Nghị định 125/2020/NĐ-CP"],
        warning: false,
      };
    }

    if (domain === "tndn") {
      return {
        domain: domain,
        intent: "missing_context",
        risk: "MEDIUM",
        title: "Chưa đủ căn cứ để kết luận ưu đãi thuế TNDN.",
        body:
          "Ưu đãi thuế TNDN phụ thuộc lĩnh vực, địa bàn, loại dự án, giấy chứng nhận đầu tư và thời điểm áp dụng. Demo sẽ hỏi thêm thông tin thay vì tự suy đoán.",
        citations: ["Luật Thuế thu nhập doanh nghiệp", "Nghị định 320/2025/NĐ-CP"],
        warning: false,
      };
    }

    return {
      domain: domain,
      intent: "general_tax_lookup",
      risk: "LOW",
      title: "Chưa đủ thông tin để xác định chính xác nhóm nghĩa vụ thuế.",
      body:
        "Bạn vui lòng nêu rõ loại thuế hoặc nghiệp vụ đang hỏi, ví dụ: thuế TNCN từ tiền lương, thuế GTGT, thuế TNDN, hóa đơn hoặc xử phạt. Nếu là tình huống cụ thể, cần thêm số tiền, kỳ tính thuế và đối tượng áp dụng.",
      citations: ["Kho dữ liệu văn bản thuế đã xử lý"],
      warning: false,
    };
  }

  function extractMillionAmount(question) {
    var text = question.toLowerCase().replace(/,/g, ".");
    var match = text.match(/(\d+(?:\.\d+)?)\s*(triệu|trieu)/);
    if (!match) return 0;
    return Number(match[1]);
  }

  function renderAnswer(answer) {
    var html =
      "<h2>" +
      escapeHtml(answer.title) +
      "</h2>" +
      '<div class="risk-row">' +
      '<span class="risk-label">Mức rủi ro</span>' +
      '<span class="risk-badge risk-' +
      escapeHtml(answer.risk.toLowerCase()) +
      '">' +
      escapeHtml(riskText(answer.risk)) +
      "</span>" +
      "</div>" +
      "<p>" +
      escapeHtml(answer.body) +
      "</p>";
    var i;

    if (byId("strictCitation").checked && answer.citations.length) {
      html += '<div class="answer-section"><h3>Căn cứ pháp lý</h3><ul class="citation-list">';
      for (i = 0; i < answer.citations.length; i += 1) {
        html += "<li>" + escapeHtml(answer.citations[i]) + "</li>";
      }
      html += "</ul></div>";
    }

    html +=
      '<div class="answer-section"><h3>Lưu ý</h3><p>Demo đang lọc theo thời điểm hiệu lực: <strong>' +
      escapeHtml(byId("effectiveDate").value) +
      "</strong>. Thông tin này chỉ hỗ trợ tra cứu quy định, không thay thế tư vấn chính thức.</p></div>";

    return html;
  }

  function textToHtml(value) {
    var normalized = String(value || "").trim();
    if (!normalized) return "<p>Backend không trả về nội dung trả lời.</p>";

    return (
      "<p>" +
      escapeHtml(normalized)
        .replace(/\r\n/g, "\n")
        .replace(/\n{2,}/g, "</p><p>")
        .replace(/\n/g, "<br>") +
      "</p>"
    );
  }

  function truncateText(value, maxLength) {
    var text = String(value || "").replace(/\s+/g, " ").trim();
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength - 3) + "...";
  }

  function renderBackendAnswer(data) {
    var answer = data && data.answer ? data.answer : "";
    var sources = data && Array.isArray(data.sources) ? data.sources : [];
    var html = "<h2>Trả lời từ RAG + Gemini</h2>" + textToHtml(answer);
    var i;

    if (sources.length && byId("strictCitation").checked) {
      html += '<div class="answer-section"><h3>Nguồn truy xuất từ kho luật</h3><ul class="citation-list">';
      for (i = 0; i < sources.length; i += 1) {
        html += "<li>" + escapeHtml(truncateText(sources[i], 700)) + "</li>";
      }
      html += "</ul></div>";
    }

    html +=
      '<div class="answer-section"><h3>Runtime</h3><p>API: <strong>' +
      escapeHtml(CHAT_API_URL) +
      "</strong></p></div>";

    return html;
  }

  function renderLoadingAnswer() {
    return (
      "<h2>Đang xử lý bằng RAG + Gemini...</h2>" +
      "<p>Backend đang truy xuất văn bản luật, tạo embedding cho câu hỏi và gọi Gemini để sinh câu trả lời.</p>"
    );
  }

  function renderBackendError(error) {
    return (
      "<h2>Không gọi được backend RAG.</h2>" +
      "<p>" +
      escapeHtml(error && error.message ? error.message : error) +
      "</p>" +
      "<p>Hãy kiểm tra backend đang chạy ở <strong>" +
      escapeHtml(API_BASE_URL) +
      "</strong>, file <strong>backend/.env</strong> có <strong>GOOGLE_API_KEY</strong>, rồi thử lại.</p>"
    );
  }

  function callChatApi(question) {
    return fetch(CHAT_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question: question,
      }),
    }).then(function (response) {
      return response.text().then(function (raw) {
        var parsed = {};

        if (raw) {
          try {
            parsed = JSON.parse(raw);
          } catch (error) {
            parsed = { answer: raw };
          }
        }

        if (!response.ok) {
          throw new Error(
            parsed.detail || parsed.message || "Backend trả lỗi HTTP " + response.status
          );
        }

        return parsed;
      });
    });
  }

  function riskText(risk) {
    if (risk === "LOW") return "Thấp";
    if (risk === "MEDIUM") return "Trung bình";
    if (risk === "HIGH") return "Cao";
    if (risk === "PROHIBITED") return "Bị chặn";
    return risk;
  }

  function appendMessage(role, html, warning) {
    var article = document.createElement("article");
    var avatar = document.createElement("div");
    var bubble = document.createElement("div");

    article.className = "message " + role;
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "Bạn" : "AI";
    bubble.className = "bubble" + (warning ? " warning-bubble" : "");
    bubble.innerHTML = html;

    if (role === "user") {
      article.appendChild(bubble);
      article.appendChild(avatar);
    } else {
      article.appendChild(avatar);
      article.appendChild(bubble);
    }

    byId("messages").appendChild(article);
    scrollChatToBottom();
  }

  function scrollChatToBottom() {
    var messages = byId("messages");
    messages.scrollTop = messages.scrollHeight;
  }

  function renderMessages() {
    var active = getActiveConversation();
    var i;

    byId("messages").innerHTML = "";
    for (i = 0; i < active.messages.length; i += 1) {
      appendMessage(active.messages[i].role, active.messages[i].html, active.messages[i].warning);
    }
  }

  function renderConversationList() {
    var html = "";
    var i;

    for (i = 0; i < state.conversations.length; i += 1) {
      var item = state.conversations[i];
      var activeClass = item.id === state.activeId ? " active" : "";
      html +=
        '<div class="conversation-row">' +
        '<button type="button" class="conversation-item' +
        activeClass +
        '" data-chat-id="' +
        escapeHtml(item.id) +
        '">' +
        "<strong>" +
        escapeHtml(item.title) +
        "</strong><span>" +
        Math.max(item.messages.length - 1, 0) +
        " tin nhắn</span></button>" +
        '<button type="button" class="conversation-delete" data-delete-chat-id="' +
        escapeHtml(item.id) +
        '">Xóa</button></div>';
    }

    byId("conversationList").innerHTML = html || '<p class="empty-state">Chưa có cuộc trò chuyện nào.</p>';
  }

  function renderAudit() {
    byId("auditLog").textContent = JSON.stringify(getActiveConversation().audit, null, 2);
  }

  function renderAll() {
    var active = getActiveConversation();
    renderConversationList();
    renderMessages();
    renderAudit();
    byId("currentChatTitle").textContent = active.title;
  }

  function submitQuestion() {
    var question = byId("questionInput").value.trim();
    var active;
    var audit;
    var userMessage;
    var botMessage;
    var botIndex;

    if (!question || state.isSubmitting) return;

    byId("questionInput").value = "";
    byId("submitBtn").disabled = true;
    byId("submitBtn").textContent = "Đang gửi...";
    state.isSubmitting = true;

    active = getActiveConversation();

    userMessage = {
      role: "user",
      html: "<p>" + escapeHtml(question) + "</p>",
      warning: false,
    };
    botMessage = {
      role: "bot",
      html: renderLoadingAnswer(),
      warning: false,
    };

    active.messages.push(userMessage);
    active.messages.push(botMessage);
    botIndex = active.messages.length - 1;

    if (active.title === DEFAULT_TITLE) {
      active.title = question.length > 42 ? question.slice(0, 42) + "..." : question;
    }

    audit = {
      user_question: question,
      mode: "rag_gemini_backend",
      status: "calling_backend",
      api_url: CHAT_API_URL,
      effective_on: byId("effectiveDate").value,
      created_at: nowIso(),
    };

    active.audit = audit;
    active.updatedAt = nowIso();
    safeWriteStorage();
    appendMessage(userMessage.role, userMessage.html, userMessage.warning);
    appendMessage(botMessage.role, botMessage.html, botMessage.warning);
    renderConversationList();
    renderAudit();
    byId("currentChatTitle").textContent = active.title;
    scrollChatToBottom();

    callChatApi(question)
      .then(function (data) {
        active.messages[botIndex] = {
          role: "bot",
          html: renderBackendAnswer(data),
          warning: false,
        };
        active.audit = {
          user_question: question,
          mode: "rag_gemini_backend",
          status: "completed",
          api_url: CHAT_API_URL,
          source_count: data && Array.isArray(data.sources) ? data.sources.length : 0,
          effective_on: byId("effectiveDate").value,
          created_at: nowIso(),
        };
      })
      .catch(function (error) {
        active.messages[botIndex] = {
          role: "bot",
          html: renderBackendError(error),
          warning: true,
        };
        active.audit = {
          user_question: question,
          mode: "rag_gemini_backend",
          status: "backend_error",
          api_url: CHAT_API_URL,
          error: error && error.message ? error.message : String(error),
          created_at: nowIso(),
        };
      })
      .finally(function () {
        active.updatedAt = nowIso();
        state.isSubmitting = false;
        byId("submitBtn").disabled = false;
        byId("submitBtn").textContent = "Gửi";
        safeWriteStorage();
        renderAll();
        scrollChatToBottom();
      });
  }

  function deleteConversation(id) {
    var kept = [];
    var i;

    for (i = 0; i < state.conversations.length; i += 1) {
      if (state.conversations[i].id !== id) kept.push(state.conversations[i]);
    }

    state.conversations = kept;
    if (!state.conversations.length) {
      createConversation();
    } else if (state.activeId === id) {
      state.activeId = state.conversations[0].id;
    }

    safeWriteStorage();
    renderAll();
  }

  function readDataFromTarget(target, attributeName) {
    var node = target;
    while (node && node !== byId("conversationList")) {
      if (node.getAttribute && node.getAttribute(attributeName)) {
        return node.getAttribute(attributeName);
      }
      node = node.parentNode;
    }
    return "";
  }

  function bindEvents() {
    byId("chatForm").addEventListener("submit", function (event) {
      event.preventDefault();
      submitQuestion();
    });

    byId("submitBtn").addEventListener("click", function (event) {
      event.preventDefault();
      submitQuestion();
    });

    byId("questionInput").addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submitQuestion();
      }
    });

    byId("newChatBtn").addEventListener("click", function () {
      createConversation();
      renderAll();
      byId("questionInput").focus();
    });

    byId("saveChatBtn").addEventListener("click", function () {
      safeWriteStorage();
    });

    byId("conversationList").addEventListener("click", function (event) {
      var deleteId = readDataFromTarget(event.target, "data-delete-chat-id");
      var chatId;

      if (deleteId) {
        if (window.confirm("Xóa cuộc trò chuyện này khỏi trình duyệt?")) {
          deleteConversation(deleteId);
        }
        return;
      }

      chatId = readDataFromTarget(event.target, "data-chat-id");
      if (chatId) {
        state.activeId = chatId;
        renderAll();
      }
    });
  }

  function init() {
    var rawItems = safeReadStorage();
    var i;
    var clean;

    byId("effectiveDate").value = today();

    for (i = 0; i < rawItems.length; i += 1) {
      clean = normalizeConversation(rawItems[i]);
      if (clean) state.conversations.push(clean);
    }

    if (!state.conversations.length) createConversation();
    state.activeId = state.conversations[0].id;

    bindEvents();
    renderAll();
    window.RAG_TAXBOT_READY = true;
  }

  window.addEventListener("error", function (event) {
    var log = byId("auditLog");
    if (!log) return;
    log.textContent = JSON.stringify(
      {
        status: "frontend_error",
        message: event.message,
        created_at: nowIso(),
      },
      null,
      2
    );
  });

  init();
})();
