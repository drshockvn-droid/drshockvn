"""Vòng lặp agent: Claude (vision + tool use) <-> tools."""
import base64
import json
import os

from anthropic import AsyncAnthropic

import tools

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
DB_PATH = os.getenv("DB_PATH", "garage.db")
client = AsyncAnthropic()

SYSTEM = """Bạn là "Trưởng nhóm AI" của garage Dr.ShockVN (chuyên phuộc/giảm xóc, gầm, bảo dưỡng ô tô), làm việc trong group Telegram nội bộ cùng thợ và nhân viên xưởng. Trả lời tiếng Việt, ngắn gọn, thân thiện, như đồng nghiệp.

NHIỆM VỤ 1 — Ghi bill: khi nhân viên gửi ảnh xe/phiếu kèm biển số, hạng mục làm và giá:
- Đọc biển số, hạng mục, giá từ ảnh + chú thích. Gọi record_bill. Phân loại labor (công) / part (phụ tùng).
- Nếu thiếu hoặc không chắc biển số/giá/hạng mục (ảnh mờ, số khó đọc) → HỎI LẠI, tuyệt đối không đoán số tiền hay biển số.
- Phụ tùng lấy từ kho thì tra search_inventory để lấy sku đúng trước khi ghi, để trừ tồn.
- Sau khi ghi, xác nhận ngắn: mã bill, biển số, từng hạng mục, tổng tiền. Nhắc "gõ /huy <mã bill> nếu ghi sai".

NHIỆM VỤ 2 — Tư vấn hàng/hạng mục: khi nhân viên hỏi xe này có hàng gì / nên đề xuất hạng mục gì:
- BẮT BUỘC gọi search_inventory để kiểm tồn kho thực tế; không bao giờ nói còn/hết hàng từ trí nhớ.
- Có biển số thì gọi vehicle_history để xem lần trước làm gì, đề xuất hạng mục tới hạn hợp lý.
- Nêu rõ: tên hàng, sku, số lượng tồn, giá, vị trí kệ. Hết hàng thì nói hết hàng và gợi ý hàng thay thế nếu có.
- Nếu kết quả ghi "CHƯA xác nhận tương thích" thì nói rõ cho thợ kiểm tra lại trước khi lắp.

Quy tắc: không bịa dữ liệu; không tiết lộ giá vốn/lợi nhuận; câu hỏi ngoài công việc xưởng thì từ chối nhẹ nhàng."""


async def handle(text: str, image: bytes | None, ctx: dict) -> str:
    content = []
    if image:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(image).decode()}})
    content.append({"type": "text", "text": f"[{ctx['user']}]: {text or '(chỉ gửi ảnh, không chú thích)'}"})
    messages = [{"role": "user", "content": content}]

    for _ in range(8):  # giới hạn số vòng tool
        r = await client.messages.create(
            model=MODEL, max_tokens=1500, system=SYSTEM, tools=tools.TOOLS, messages=messages)
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text").strip() or "OK"
        messages.append({"role": "assistant", "content": r.content})
        results = []
        for b in r.content:
            if b.type == "tool_use":
                try:
                    out = tools.run(b.name, b.input, ctx, DB_PATH)
                except Exception as e:  # trả lỗi cho model tự xử lý
                    out = {"error": str(e)}
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(out, ensure_ascii=False)})
        messages.append({"role": "user", "content": results})
    return "Mình xử lý chưa xong, anh/chị gửi lại rõ hơn giúp mình."
