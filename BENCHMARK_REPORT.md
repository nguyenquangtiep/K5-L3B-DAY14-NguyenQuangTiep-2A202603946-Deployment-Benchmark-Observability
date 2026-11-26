# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyen Quang Tiep  
**Ngày chạy:** 26/11/2026  
**Môi trường:** Windows, WSL Ubuntu, Python 3.11, Docker Desktop

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Hạn chế độ trễ của phần lớn request, không chỉ giá trị trung bình. |
| Error rate `/ask` | ≤ 2% | Kiểm soát tỷ lệ request thất bại; phù hợp ngưỡng của load_test.py. |
| Accuracy trên golden dataset | ≥ 80% | Quality gate ban đầu; sau khi sửa KB đặt ngưỡng 100% để kiểm chứng đủ 23 câu. |

Các ngưỡng trên dùng cho benchmark local. Alert của stack production mô phỏng có ngưỡng riêng: error rate > 5%, p95 > 1 giây.

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---:|---:|---:|---:|---:|---|
| 1 | 4.41 | 185.6 | 220.5 | 1688.0 | 1.00% | PASS |
| 10 | 47.07 | 190.5 | 220.8 | 1664.7 | 0.67% | PASS |
| 50 | 119.41 | 199.8 | 249.9 | 1698.3 | 1.00% | PASS |
| 100 | 49.88 | 635.9 | 4108.7 | 4528.3 | 1.00% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. Mỗi lần chạy có 300 request. RPS tăng đến concurrency 50, sau đó giảm tại 100, đồng thời p95 vượt SLO. Concurrency 50 đạt throughput cao nhất trong bốn mức đã thử, không phải giá trị tối ưu đã được chứng minh. Có thể xảy ra tranh chấp tài nguyên hoặc chờ xử lý ở tải cao; chưa profiling nên chưa xác định được nút thắt chính xác.

Evidence: `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json` (cùng thư mục `reports/`).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---:|---:|---:|
| 0 | 190.9 | 220.0 | 230.2 |
| 0.03 (mặc định) | 229.4 | 221.6 | 1692.8 |
| 0.1 | 350.0 | 1698.4 | 1710.0 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

Ở concurrency 20, 300 request mỗi lần, p99 phản ứng rõ ngay khi slow rate tăng lên 3%, trong khi p95 gần như không đổi. Khi slow rate tăng lên 10%, p95 cũng vượt SLO. Average 350 ms vẫn dưới 500 ms nhưng p95 lên tới 1698.4 ms, nên average có thể che khuất trải nghiệm của nhóm request chậm. Error rate tương ứng là 0%, 1.67%, 2%; kết quả SLO là PASS, PASS, FAIL.

Evidence: `reports/load_v2_slow_0.json`, `reports/load_v2_slow_0.03.json`, `reports/load_v2_slow_0.1.json`.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---:|---:|---:|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.7 | 109.0 | 116.4 |
| Tổng cost (USD) | 0.000399 | 0.000759 | 0.000814 |
| Cost / câu đúng (USD) | 0.00039915 | 0.00003616 | 0.00003540 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm entry JWT, giải thích claims, chữ ký và thời gian hết hạn; phân biệt API key. |
| scaling-03 | cpu, memory, custom metrics | Thêm entry Kubernetes HPA, mô tả các metric dùng để tự động scale Pod. |

Chỉ sửa knowledge base tại `develop/utils/mock_llm.py`, không sửa golden dataset. Eval lại với baseline v2 và min-accuracy 1.0: 23/23 đúng, cải thiện 2 câu và 0 regression. Thử v1 với baseline v2 phát hiện 20 regression, exit code 1 theo kết quả terminal.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

v2 tốn nhiều token và tổng chi phí hơn v1 nhưng chi phí trên mỗi câu đúng thấp hơn đáng kể. p50 lần lượt là 152.9, 182.3, 188.5 ms; p95 lần lượt 186.9, 264.7, 219.9 ms. Không kết luận sửa KB làm giảm latency từ một lần đo duy nhất. Quality gate kiểm tra accuracy và regression, có thể dùng exit code để chặn deployment trong CI/CD. Chưa triển khai workflow CI riêng cho gate. Dataset chỉ có 23 câu và dùng Mock LLM, không đại diện cho toàn bộ câu hỏi thực tế.

Evidence: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] [Dashboard Grafana khi đang có tải](screenshots/grafana-dashboard.png) (Golden Signals).
- [x] [Một trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png) (LLM call chiếm phần lớn thời gian).
- [x] [Một trace lỗi trong Jaeger](screenshots/jaeger-error-trace.png) (event `exception`).
- [x] [Trang Alerts của Prometheus](screenshots/prometheus-alert-firing.png) với hai alert cùng firing: AgentHighErrorRate và AgentHighLatencyP95.

Stack gồm Agent, Nginx, Prometheus, Grafana, Jaeger và Locust. Agent chạy 1 worker/container để tránh sai lệch metric trong bộ nhớ từng process. Prometheus scrape metric, Grafana hiển thị dashboard, Jaeger nhận OTLP traces; JSON log liên kết theo trace_id. Khi khởi chạy, Dockerfile ban đầu bị lỗi import uvicorn do đường dẫn user-site không khớp home directory. Đã sửa cài dependencies vào /install ở builder và copy sang /usr/local ở runtime; giữ multi-stage, non-root, healthcheck và một worker. Sau khi sửa, Agent healthy và `/health` qua Nginx trả HTTP 200. Xung đột port 8080 cũng đã được xử lý.

**Exercise 7.4 — Observability Stack Questions**

1. **p95 và average latency khác nhau như thế nào?**

   Trong benchmark scaling với 1 instance, endpoint /ask có average latency 242.26 ms và p95 250 ms. Với 3 instances, average latency là 236.76 ms và p95 là 260 ms. Ảnh Grafana khi có tải ghi nhận p95 là 291.51 ms, error rate 0.21% và traffic 8.6 requests/s. Average chính xác tại thời điểm chụp ảnh chưa được ghi lại. Khoảng cách giữa average và các percentile cao phản ánh tail latency; một nhóm request chậm có thể ảnh hưởng trải nghiệm người dùng dù average vẫn thấp.

2. **Nginx có phân phối traffic đều giữa các instance không?**

   Panel Requests/s theo instance trong thí nghiệm E cho thấy ở giai đoạn có 3 instances, mỗi instance xử lý khoảng 6 requests/s. Traffic được phân phối tương đối đồng đều. Khi chỉ còn 2 instances hoạt động trong giai đoạn trước đó, mỗi instance xử lý khoảng 9 requests/s.

3. **Vì sao input tokens/s có thể lớn hơn output tokens/s?**

   Input tokens bao gồm câu hỏi, system prompt và context được retrieval bổ sung. Vì vậy input có thể lớn hơn output. Trong slow trace thực tế, input là 76 tokens và output là 39 tokens. Tuy nhiên, tỷ lệ này phụ thuộc độ dài câu trả lời; dashboard tổng hợp không phải lúc nào cũng có input tokens/s lớn hơn output tokens/s.

4. **Vì sao Nginx chặn endpoint /metrics?**

   Cấu hình nginx/nginx.conf định nghĩa location = /metrics trả về HTTP 404. Điều này ngăn truy cập công khai vào metrics nội bộ, tránh tiết lộ thông tin về traffic, chi phí và tình trạng hệ thống. Prometheus vẫn có thể scrape trực tiếp Agent thông qua Docker network. HTTP 404 là kết quả theo cấu hình; chưa lưu riêng output curl của endpoint này.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → quan sát firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | AgentHighErrorRate | Chưa ghi chính xác | Error rate 20.61% (Grafana), 19.45% (Prometheus); p95 290.28 ms |
| B | `MOCK_SLOW_RATE=0.3` (giữ error rate 0.2) | AgentHighLatencyP95 và AgentHighErrorRate | Chưa ghi chính xác | p95 1.90 s, error rate 19.37%, 15.1 req/s |
| C | `LLM_MODEL=mock-llm-large` | LLMCostBurnRateHigh | 235 giây (3 phút 55 giây) | LLM cost (1h) 4.4189 USD; p95 664.19 ms |
| D | `docker pause` 1 instance | AgentInstanceDown; LLMCostBurnRateHigh cũng đang firing | 221 giây (3 phút 41 giây) | Instances up 2/3, traffic 18 req/s, error rate 0.81%, p95 294.47 ms |
| E | `AGENT_VERSION=v1` | Không có alert firing | N/A | Tokens/s giảm; response xác nhận agent_version=v1 |

Thời gian thực nghiệm C và D được tính từ thời điểm bắt đầu thay đổi cấu hình đến thời điểm quan sát thấy alert ở trạng thái firing. Đây không nhất thiết là thời điểm chính xác alert vừa chuyển sang firing, do có độ trễ quan sát thủ công.

Các giá trị `for` là thời gian duy trì điều kiện của rule, không phải số đo thời gian thực tế từ lúc đổi cấu hình. A hiển thị Active Since 4m 28.049s khi chụp, không dùng thay thế thời gian tới firing. B giữ lỗi A để kiểm chứng hai alert đồng thời, nên không phải hai thí nghiệm độc lập. C sử dụng chi phí mô phỏng; cost alert tính `rate` trên 5 phút quy đổi USD/giờ, khác tổng cost trong cửa sổ 1 giờ. Cost alert từng firing ở model small và còn firing trong D, có thể liên quan mức tải hoặc cửa sổ metric lịch sử. D cho thấy hai Agent vẫn phục vụ request; chưa có bằng chứng HTTP 504 từ Locust, và lỗi tại Nginx không nhất thiết xuất hiện trong metric Agent.

Evidence: `screenshots/experiment-a-alert.png`, `experiment-a-grafana.png`, `experiment-b-grafana.png`, `prometheus-alert-firing.png`, `experiment-c-alert.png`, `experiment-c-grafana.png`, `experiment-d-alert.png`, `experiment-d-grafana.png`, `experiment-e-alert.png`, `experiment-e-grafana.png` (cùng thư mục screenshots/).

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Agent v1 trả lời câu hỏi “Prometheus thu thập metrics theo cơ chế push hay pull?” bằng “Câu hỏi hay! Điều này phụ thuộc vào kiến trúc hệ thống và yêu cầu cụ thể của bạn.”, không nêu cơ chế pull. Response xác nhận agent_version=v1, 39 input tokens, 20 output tokens, 172.7 ms LLM latency, 0.00001785 USD. Trong khi đó, ảnh Prometheus có cả 4 alert Inactive. Eval ở CP7 cho thấy v1 đạt 4.35% so với v2 đã sửa đạt 100%. Đây là bằng chứng metric hạ tầng không đủ để phát hiện quality regression. Cần eval định kỳ trên golden dataset và mẫu dữ liệu thực, quality gate trước deployment, giám sát accuracy/relevance và cảnh báo khi chất lượng giảm. Panel retrieval sử dụng rate 5 phút và ảnh có lịch sử v2, không kết luận hit ratio đã về 0.

Unit test alert rules:

```text
Processing test file: /p/alert_rules_test.yml
  SUCCESS
```

### 4.3 Debug bằng trace

Trace chậm đã chọn:

- `trace_id`: `42ab701fb00b2f98a192520b5488d71d`
- Tổng thời gian: 1692.1 ms (Jaeger hiển thị 1.7 s).
- Span xử lý chiếm nhiều thời gian nhất: `chat mock-llm-small` (1661.7 ms theo llm_call log, khoảng 98.20% tổng thời gian).
- Retrieval: 26.6 ms; HTTP status 200; 76 input tokens, 39 output tokens, cost 0.000035 USD.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts":"2026-11-26T10:41:54.335687+00:00","level":"INFO","service":"observable-agent","instance":"d66226d73ebc","event":"llm_call","trace_id":"42ab701fb00b2f98a192520b5488d71d","span_id":"628cab976b30fdca","request_id":"11fb47236946","model":"mock-llm-small","agent_version":"v2","input_tokens":76,"output_tokens":39,"cost_usd":3.5e-05,"llm_ms":1661.7}
```

```json
{"ts":"2026-11-26T10:41:54.336094+00:00","level":"INFO","service":"observable-agent","instance":"d66226d73ebc","event":"http_request","trace_id":"42ab701fb00b2f98a192520b5488d71d","span_id":"628cab976b30fdca","request_id":"11fb47236946","method":"POST","route":"/ask","status":200,"ms":1692.1}
```

LLM call chiếm phần lớn latency của request này. Không khẳng định đây là trace chậm nhất toàn bộ hệ thống hoặc nút thắt duy nhất.

**Error Trace:** `382642a373f48fce61d5be7cf791e36e`, request `ba2470b3f5a3`, instance `ba62fb1b78a4`. Jaeger hiển thị 122 ms, event exception tại 120.76 ms, error.type=upstream_unavailable, exception `utils.mock_llm.LLMError`. Log xác nhận HTTP 503, duration 121.3 ms.

```json
{"ts":"2026-11-26T14:29:16.622502+00:00","level":"INFO","service":"observable-agent","instance":"ba62fb1b78a4","event":"llm_error","trace_id":"382642a373f48fce61d5be7cf791e36e","span_id":"0f5d6eeda7b168f0","request_id":"ba2470b3f5a3","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

```json
{"ts":"2026-11-26T14:29:16.622799+00:00","level":"INFO","service":"observable-agent","instance":"ba62fb1b78a4","event":"http_request","trace_id":"382642a373f48fce61d5be7cf791e36e","span_id":"0f5d6eeda7b168f0","request_id":"ba2470b3f5a3","method":"POST","route":"/ask","status":503,"ms":121.3}
```

Trace ID chung liên kết log và Jaeger, giúp định vị lỗi upstream thay vì chỉ quan sát mã HTTP. Request lỗi nhanh hơn request chậm thành công, vì vậy latency thấp không đồng nghĩa chất lượng dịch vụ tốt.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---:|---:|---:|---:|---:|
| 1 | 65.90 | 190 | 240 | 1700 | 81 (1.04%) |
| 3 | 65.97 | 190 | 250 | 1700 | 74 (0.94%) |

Cùng điều kiện: 100 users, spawn rate 10 users/s, 2 phút, v2, mock-llm-small, slow rate 0.03 và error rate 0.01. Số liệu lấy từ dòng Aggregated (bao gồm `/ask` và `/health`) của `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv`. Tổng request lần lượt 7809 và 7889.

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Không cải thiện đáng kể throughput; p95 tăng nhẹ từ 240 lên 250 ms, p99 không đổi. Riêng `/ask`, RPS lần lượt 59.54 và 59.78, p95 250 và 260 ms, error rate 1.15% và 1.04%; cả hai đạt SLO benchmark CP7. Một instance có thể đã đủ ở tải này với async processing, mock latency và thời gian nghỉ 0.5–2 giây của Locust. Trace chậm ở mục 4.3 cho thấy LLM call chiếm khoảng 98.20% thời gian của request được chọn. Đây là bằng chứng cho một request, chưa chứng minh bottleneck toàn hệ thống. Không kết luận scaling làm giảm tỷ lệ lỗi vì lỗi mô phỏng ngẫu nhiên và mỗi cấu hình chỉ chạy một lần. Thí nghiệm D còn cho thấy giá trị về availability dù throughput không tăng đáng kể.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Cần đo RPS, p95/p99 và error rate cùng nhau; trung bình không phản ánh tail latency, tăng concurrency hoặc replica không bảo đảm throughput tăng tuyến tính.
  2. Metrics và alerts phát hiện sự cố, traces và JSON log cùng trace_id giúp định vị nguyên nhân. Cần giám sát cả latency, error, availability và chi phí AI.
  3. Hạ tầng không có alert vẫn có thể trả lời sai. Evaluation và quality gate là cần thiết để phát hiện quality regression trước và sau deployment.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

Bổ sung metric error/timeout ở Nginx và synthetic health check bên ngoài; metric queue, CPU/RAM và latency upstream; cost per successful answer và tốc độ tiêu ngân sách; quality score trên bộ eval định kỳ, regression và feedback người dùng. Không dùng user_id hoặc trace_id làm metric label có cardinality cao. Dùng sampling trace phù hợp tải và không ghi secrets vào log.
