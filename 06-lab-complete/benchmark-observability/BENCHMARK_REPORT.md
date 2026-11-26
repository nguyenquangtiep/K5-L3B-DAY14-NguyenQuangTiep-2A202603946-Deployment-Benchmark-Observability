# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nguyễn Quang Tiệp
**Ngày chạy:** 26/11/2026
**Môi trường:** (vd MacBook M2, Docker Desktop 4 CPU / 8GB RAM)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Đảm bảo ít nhất 95% request có thời gian phản hồi trong ngưỡng chấp nhận được, hạn chế ảnh hưởng của tail latency. |
| Error rate `/ask` | ≤ 2% | Đảm bảo ít nhất 98% request được xử lý thành công trong bài load test. |
| Accuracy trên golden dataset | ≥ 80% | Đảm bảo chất lượng câu trả lời tối thiểu trước khi triển khai. Sau khi sửa Knowledge Base, quality gate được nâng lên 100% và không cho phép regression. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 10 | | | | | | |
| 50 | | | | | | |
| 100 | | | | | | |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

...

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | | | |
| 0.03 (mặc định) | | | |
| 0.1 | | | |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

...

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.7 | 109.0 | 116.4 |
| Tổng cost (USD) | 0.000399 | 0.000759 | 0.000814 |
| Cost / câu đúng (USD) | 0.00039915 | 0.00003616 | 0.00003540 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Bổ sung entry về JWT và API key vào KNOWLEDGE_BASE. Giải thích JWT chứa claims, có thời gian hết hạn và được xác minh bằng chữ ký. |
| scaling-03 | cpu, memory, custom metrics | Bổ sung entry về Kubernetes HPA, giải thích cơ chế điều chỉnh số lượng Pod dựa trên CPU, memory và custom metrics. |

Sau khi sửa KNOWLEDGE_BASE, Agent v2 đạt accuracy 100% (23/23), cải thiện 2 câu và không có regression so với baseline v2 ban đầu. Quality gate với min-accuracy 1.0 trả PASS.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent v1 không có retrieval nên sử dụng ít token và có tổng chi phí thấp hơn, nhưng chỉ trả lời đúng 1/23 câu hỏi.

Agent v2 bổ sung retrieval từ Knowledge Base, giúp accuracy tăng lên 91.30%. Sau khi bổ sung hai tài liệu còn thiếu, accuracy đạt 100%.

Agent v2 Fixed có tổng chi phí cao hơn v1 nhưng chi phí trên mỗi câu trả lời đúng giảm từ 0.00039915 USD xuống 0.00003540 USD, tương đương giảm khoảng 91.13%.

Retrieval làm tăng độ dài context, số token và có thể làm tăng latency. Tuy nhiên, mức cải thiện chất lượng lớn hơn đáng kể so với chi phí tăng thêm trong thí nghiệm này.

Kết quả latency từ bộ eval chỉ mang tính tham khảo vì tập dữ liệu có 23 câu hỏi. Benchmark hiệu năng cần sử dụng kết quả load test ở mục 2.

**Regression Test và Quality Gate trong CI/CD:**

Chạy Agent v1 với baseline của Agent v2:

```bash
python eval/run_eval.py \
  --url http://localhost:8001 \
  --baseline reports/eval_v2.json \
  --min-accuracy 0.8

echo "Exit code: $?"
```

Kết quả thực tế:

- Accuracy: 4.35% (1/23).
- Improved: 0.
- Regression: 20 câu.
- Quality Gate: FAIL.
- Exit code: 1.

Trong GitHub Actions, có thể khởi chạy Agent phiên bản mới và sử dụng run_eval.py để kiểm tra với baseline của phiên bản đã được chấp nhận. Script trả exit code 0 nếu đạt ngưỡng accuracy và không có regression; ngược lại trả exit code 1 khiến CI job thất bại. Khi job này được cấu hình là required status check, Pull Request không thể merge nếu chất lượng Agent suy giảm.

**Limitations:** Agent sử dụng Mock LLM, keyword matching và Knowledge Base nhỏ. Accuracy 100% chỉ phản ánh kết quả trên golden dataset hiện tại, chưa chứng minh khả năng tổng quát hóa đối với câu hỏi ngoài tập dữ liệu. Chi phí được tính theo mô hình giả lập.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
