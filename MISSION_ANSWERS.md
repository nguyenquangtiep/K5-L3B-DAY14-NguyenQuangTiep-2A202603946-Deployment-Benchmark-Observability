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

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. **Base image:** `python:3.11`, cung cấp môi trường Python và các thành phần hệ thống cần thiết để chạy ứng dụng.
2. **Working directory:** `/app`, là thư mục làm việc bên trong container.
3. **Why COPY requirements.txt first?** Tận dụng Docker layer cache. Khi source code thay đổi nhưng requirements.txt không đổi, Docker có thể tái sử dụng layer đã cài dependencies.
4. **CMD vs ENTRYPOINT:** CMD cung cấp lệnh hoặc tham số mặc định có thể ghi đè khi chạy container. ENTRYPOINT xác định chương trình chính được thực thi khi container khởi động.

### Exercise 2.2: Build and run

Build command:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
```

Health check result:

```text
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":25.7,"container":true}
```

Agent API result:

```text
HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

**Observation:** Agent được đóng gói và chạy thành công trong Docker container. Cả health check và agent endpoint đều trả về HTTP 200 OK.

### Exercise 2.3: Image size comparison

Actual Docker image results:

```text
my-agent:advanced   4bd98499d2ad   240MB    57.4MB
my-agent:develop    579f1f659cd0   1.67GB   426MB
```

- Develop: 1670 MB.
- Production: 240 MB.
- Difference: 85.63% reduction.
- Saved storage: approximately 1430 MB.

Calculation:

`(1670 - 240) / 1670 × 100 = 85.63%`

**Stage 1 — Builder:** Cài đặt dependencies và các công cụ cần thiết trong quá trình build.

**Stage 2 — Runtime:** Chỉ sao chép dependencies đã cài đặt và source code cần thiết để chạy ứng dụng, sử dụng Python slim và non-root user.

**Conclusion:** Multi-stage build kết hợp với slim base image giúp giảm kích thước image, loại bỏ các công cụ build không cần thiết và cải thiện tính bảo mật. Image Production có kích thước 240 MB, đáp ứng mục tiêu dưới 500 MB.

### Exercise 2.4: Docker Compose stack

**Architecture diagram:**

```text
Client (curl)
     |
     v
Nginx (port 80)
     |
     v
Agent (FastAPI, port 8000)
     |
     +-- Redis (port 6379)
     |
     +-- Qdrant (port 6333)
```

Redis và Qdrant là các dịch vụ phụ trợ được cấu hình trong Docker Compose. Agent mẫu chưa trực tiếp truy vấn chúng trong luồng xử lý /ask.

**Services:**

| Service | Purpose | Actual status |
|---|---|---|
| Agent | Xử lý câu hỏi bằng Mock LLM | Up (healthy) |
| Nginx | Reverse proxy và chuyển tiếp request | Up |
| Redis | Hạ tầng cache và session | Up (healthy) |
| Qdrant | Vector database phục vụ RAG | Up (healthy) |

**Test results:**

Health check:

```text
HTTP/1.1 200 OK
Server: nginx

{"status":"ok","uptime_seconds":34.0,"version":"2.0.0","timestamp":"2026-11-26T07:52:30.015744"}
```

Agent API:

```text
HTTP/1.1 200 OK
Server: nginx

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

**Observation:** Tất cả 4 service được khởi chạy thành công bằng Docker Compose. Nginx tiếp nhận request từ client và chuyển tiếp đến Agent thông qua mạng nội bộ Docker. Cả endpoint /health và /ask đều trả về HTTP 200 OK.

**Conclusion:** Docker Compose giúp quản lý nhiều container, network, dependencies và health check trong cùng một cấu hình, đơn giản hóa việc triển khai hệ thống gồm nhiều dịch vụ.