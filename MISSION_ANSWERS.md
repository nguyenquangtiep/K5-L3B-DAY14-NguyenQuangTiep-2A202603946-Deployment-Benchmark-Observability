# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. **Hardcoded API key:** API key được khai báo trực tiếp trong source code, có nguy cơ bị lộ khi đưa code lên GitHub.
2. **Hardcoded database URL:** Thông tin kết nối database được đặt cố định, gây khó khăn khi chuyển đổi môi trường.
3. **Hardcoded configuration:** Các cấu hình như DEBUG, MAX_TOKENS và PORT không được quản lý qua biến môi trường.
4. **Insecure logging:** Sử dụng `print()` và ghi API key ra log, gây rủi ro bảo mật và khó quản lý log tập trung.
5. **Missing health check:** Không có endpoint `/health` để nền tảng triển khai kiểm tra trạng thái ứng dụng.
6. **Localhost binding:** Server chỉ lắng nghe trên localhost, gây hạn chế khi triển khai trong container.
7. **Development reload mode:** `reload=True` không phù hợp với môi trường production.
8. **Missing explicit lifecycle management:** Không có cơ chế quản lý vòng đời ứng dụng riêng để giải phóng tài nguyên khi shutdown.

### Exercise 1.2: Basic version test results

Test command:

```bash
curl -i -X POST "http://localhost:8000/ask?question=Hello"
```

Actual result:

```text
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:26:37 GMT
server: uvicorn
content-length: 126
content-type: application/json

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

**Observation:** Agent khởi động thành công trên localhost:8000, nhận câu hỏi và trả về HTTP 200 OK. Tuy nhiên, ứng dụng vẫn tồn tại các anti-pattern về configuration, security, logging và reliability nên chưa sẵn sàng cho production.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---|---|---|---|
| Configuration | Hardcoded | Environment variables | Cho phép thay đổi cấu hình giữa các môi trường mà không cần sửa source code. |
| Secrets | Hardcoded trong code | Đọc từ biến môi trường | Giảm nguy cơ làm lộ thông tin bí mật. |
| Health check | Không có | GET /health | Giúp nền tảng triển khai xác định ứng dụng còn hoạt động hay không. |
| Readiness check | Không có | GET /ready | Giúp xác định ứng dụng đã sẵn sàng tiếp nhận request hay chưa. |
| Logging | print() | Structured JSON logging | Hỗ trợ theo dõi, tìm kiếm và phân tích log. |
| Shutdown | Không có lifecycle riêng | Graceful shutdown và lifespan | Hỗ trợ hoàn thành request đang xử lý và giải phóng tài nguyên trước khi tắt. |
| Host | localhost | 0.0.0.0 | Cho phép ứng dụng nhận kết nối từ bên ngoài container. |
| Port | Cố định 8000 | Environment variable | Cho phép sử dụng port được cấp bởi nền tảng cloud. |
| Reload | Luôn bật | Phụ thuộc cấu hình debug | Tránh tự động reload không cần thiết trong production. |

**Actual test results:**

| Endpoint | HTTP status | Result |
|---|---|---|
| GET / | 200 OK | AI Agent, version 1.0.0, status running |
| GET /health | 200 OK | status: ok, uptime: 21.4 seconds |
| GET /ready | 200 OK | Endpoint trả về thành công |
| POST /ask | 200 OK | Agent trả lời câu hỏi Hello thành công |

**Conclusion:** Phiên bản develop có thể chạy và trả lời câu hỏi, nhưng còn nhiều anti-pattern. Phiên bản production cải thiện configuration, logging, health check, readiness và lifecycle management, giúp ứng dụng phù hợp hơn với môi trường triển khai thực tế.