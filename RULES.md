# RULES.md — Hard Rules for Truth-Seeking Multi-Agent Research

Các rule trong file này là **hard invariants**. Agent hoặc orchestrator không được tự ý bỏ qua.

---

## R-001 — Independence Before Interaction

Hypothesis agents phải suy luận độc lập trước khi thấy output của agent khác.

**Bắt buộc**
- lưu initial hypothesis trước debate;
- không truyền majority opinion vào initial generation;
- mỗi hypothesis có `author_agent_id` và timestamp.

**Lý do**
Multi-agent debate có thể gây conformity và majority pressure.

---

## R-002 — Consensus Is Not Evidence

Số lượng agent đồng ý **không** được dùng làm bằng chứng cho một claim.

Không hợp lệ:

```text
4/5 agents agree => claim supported
```

Hợp lệ:

```text
experiment E-17 + artifact A-52 + verifier V-09 => claim supported
```

---

## R-003 — Separation of Duties

Không cho cùng một role vừa tạo vừa tự xác nhận kết quả chính của mình.

Tối thiểu phải tách:

```text
Hypothesis Generator != Verifier
Experiment Designer   != Independent Verifier
Experiment Runner     != Final Synthesizer
```

---

## R-004 — Every Hypothesis Must Be Falsifiable

Hypothesis thiếu prediction hoặc falsifier rõ ràng không được qua hypothesis gate.

Required:

```yaml
predictions: [...]
falsifiers: [...]
```

Nếu không thể mô tả observation nào làm hypothesis yếu đi hoặc bị bác bỏ:

```text
status = UNTESTABLE
```

---

## R-005 — Pre-register Experiment Decisions

Trước execution phải khóa:

- hypothesis version;
- dataset / split;
- baseline;
- metric;
- success threshold;
- failure threshold;
- seeds;
- control;
- ablation plan.

Thay đổi sau khi thấy kết quả phải tạo:

```text
ExperimentRevision
```

và giữ revision cũ.

---

## R-006 — Raw Evidence Is Immutable

Raw output không được overwrite.

Mỗi artifact phải có:

```yaml
artifact_id: ...
created_by: ...
created_at: ...
input_ids: [...]
tool: ...
tool_version: ...
config_hash: ...
content_hash: ...
```

Processed artifact phải trỏ về raw artifact nguồn.

---

## R-007 — Blind Verification

Independent verifier không được xem conclusion/verdict của producer trước khi tự tạo verification result ban đầu.

Verifier được xem:
- hypothesis;
- registered experiment spec;
- code;
- raw artifacts;
- environment.

Verifier không được xem trước:
- "experiment succeeded";
- final narrative;
- producer confidence;
- majority vote.

---

## R-008 — Recompute, Do Not Trust Reported Metrics

Verifier phải ưu tiên tính lại metric từ raw data.

Nếu chỉ có metric summary mà không có dữ liệu đủ để audit:

```text
verification_status = INCOMPLETE
```

---

## R-009 — Claim Scope Cannot Exceed Evidence Scope

Nếu experiment chỉ test:

```text
dataset = X
model = Y
context = 128K
```

thì không được viết:

```text
"Phương pháp này luôn tốt hơn mọi Transformer."
```

Writer phải giữ qualifiers, conditions và uncertainty.

---

## R-010 — Evidence-Gated Claims

Claim chỉ được promote nếu có evidence chain hợp lệ.

Minimum:

```text
Claim
 -> Evidence
 -> Finding
 -> Experiment
 -> Artifact
```

Claim chính còn orphan:

```text
BLOCK_FINALIZATION
```

---

## R-011 — Preserve Negative Results

Không được xóa:
- experiment fail;
- refuted hypothesis;
- null result;
- verifier disagreement;
- unsuccessful repair.

Negative result phải lưu điều kiện và nguyên nhân nếu biết.

---

## R-012 — Correctness and Novelty Are Separate

Một claim có thể:

```text
SUPPORTED_BUT_KNOWN
NOVEL_BUT_UNSUPPORTED
SUPPORTED_AND_POSSIBLY_NOVEL
```

Không được suy ra novelty từ correctness.

Không được suy ra correctness từ novelty.

---

## R-013 — Novelty Requires Search Trace

Tuyên bố `NOVEL`/`POSSIBLY_NOVEL` phải kèm:

- queries;
- databases/sources;
- search date;
- closest prior work;
- similarity/difference analysis;
- known coverage limits.

Nếu không:

```text
novelty_status = UNCHECKED
```

---

## R-014 — Citation Must Support the Claim

Citation tồn tại chưa đủ.

Phải kiểm:
1. nguồn có thật;
2. metadata đúng;
3. đoạn được cite liên quan;
4. claim không mạnh hơn nguồn;
5. source type được ghi rõ.

State:

```text
VERIFIED
PARTIAL
CONTRADICTED
UNVERIFIED
```

---

## R-015 — Source Fact != Agent Inference

Mọi research note phải phân biệt:

```yaml
type: SOURCE_FACT
```

với:

```yaml
type: AGENT_INFERENCE
```

Inference phải trỏ tới supporting facts.

---

## R-016 — Evidence Beats Confidence

`confidence: 0.95` của agent không thể thay thế evidence.

Confidence chỉ dùng để:
- prioritization;
- resource allocation;
- uncertainty reporting.

Không dùng để promote claim.

---

## R-017 — Minority Truth Must Be Preserved

Nếu một hypothesis thiểu số có evidence tốt hơn consensus, hệ thống phải giữ nó.

Không drop hypothesis chỉ vì:
- ít agent chọn;
- critic không đồng ý;
- rank ban đầu thấp.

Chỉ evidence gate được quyền bác bỏ theo scientific criteria.

---

## R-018 — No Silent Protocol Drift

Agent không được tự đổi:
- mục tiêu;
- metric;
- dataset;
- baseline;
- success criterion.

Mọi thay đổi phải có:
- reason;
- old value;
- new value;
- author;
- timestamp;
- affected claims.

---

## R-019 — Provenance Is Mandatory

Mỗi object quan trọng phải biết:

```text
who / what generated it
from which inputs
using which tool/model/config
at what time
```

Nên map theo tinh thần W3C PROV:

```text
Entity <- wasGeneratedBy - Activity
Activity <- wasAssociatedWith - Agent
Entity <- wasDerivedFrom - Entity
```

---

## R-020 — Completion Depends on Workspace State

Agent nói "done" không làm task hoàn tất.

Completion được tính bằng machine-checkable gates:

```text
schemas valid
AND evidence graph valid
AND required artifacts exist
AND verification gates pass
AND tests pass
```

---

## R-021 — Failed Verification Blocks Promotion

Nếu producer và verifier bất đồng về claim chính:

```text
status = DISPUTED
```

Không được writer tự chọn bên.

Action:
- rerun;
- third verifier;
- narrower claim;
- additional experiment.

---

## R-022 — Replication Must Be Independent Enough

Replication tốt phải thay ít nhất một nguồn phụ thuộc khi phù hợp:

- process/run;
- random seed;
- implementation;
- environment;
- verifier.

Copy cùng output không phải replication.

---

## R-023 — No Writer Hallucination

Synthesizer chỉ được dùng `validated_claim_ids`.

Nếu thông tin cần thiết không có trong graph:

```text
[UNRESOLVED]
```

không tự điền.

---

## R-024 — Contradictions Are First-Class Objects

Không ép graph thành một câu chuyện nhất quán giả tạo.

Cho phép:

```text
E1 supports C1
E2 contradicts C1
```

C1 khi đó có thể:

```text
DISPUTED
CONTEXT_DEPENDENT
UNDER_SPECIFIED
```

---

## R-025 — Checkpoints and Rollback

Mọi repair/regeneration quan trọng phải tạo checkpoint.

Nếu repair làm evidence chain xấu hơn:
- rollback;
- giữ failed branch;
- ghi lý do.

---

## R-026 — Resource Budget Cannot Change Epistemic Standards

Thiếu compute có thể làm:

```text
status = INCOMPLETE
```

nhưng không được làm:
- giảm verification gate;
- bỏ citation check rồi vẫn gọi verified;
- gọi single run là replicated.

---

## R-027 — Human Override Must Be Audited

Human có thể override, nhưng phải ghi:

```yaml
override_by: human
reason: ...
previous_state: ...
new_state: ...
```

Human override không tự biến unsupported claim thành supported claim.

---

## R-028 — Security / Tool Boundary

Agent chạy code phải:
- sandbox khi có thể;
- không execute code không rõ nguồn ngoài scope;
- không expose secrets;
- log external calls;
- không tự mở rộng quyền tool.

Research integrity không được đánh đổi lấy tool autonomy.

---

## R-029 — Final Report Must Include Uncertainty

Final docs bắt buộc có:

- supported findings;
- refuted hypotheses;
- unresolved questions;
- limitations;
- contradictory evidence;
- novelty uncertainty;
- reproduction status.

---

## R-030 — Stop Conditions

Hệ thống phải dừng/escalate nếu:

- không có test phân biệt giữa competing hypotheses;
- verifier không thể audit artifact;
- literature evidence mâu thuẫn chưa giải quyết;
- budget hết trước minimum verification;
- experiment có lỗi làm invalid result;
- safety/tool policy chặn phép kiểm chứng.

Không được "tổng hợp cho xong".

---

## Promotion matrix

| Current state | Required gate | Next state |
|---|---|---|
| IDEA | statement + mechanism | HYPOTHESIS |
| HYPOTHESIS | predictions + falsifiers | TESTABLE |
| TESTABLE | registered protocol | EXPERIMENT_REGISTERED |
| EXPERIMENT_REGISTERED | immutable execution artifacts | EXECUTED |
| EXECUTED | evidence supports prediction | SUPPORTED |
| SUPPORTED | independent verification | VERIFIED |
| VERIFIED | novelty search | NOVELTY_CHECKED |
| VERIFIED/NOVELTY_CHECKED | valid claim chain | PROVISIONAL_KNOWLEDGE |

Không có đường tắt.

---

## Research basis

- **Towards an AI co-scientist** — https://arxiv.org/abs/2502.18864
- **Automated Hypothesis Validation with Agentic Sequential Falsifications (Popper)** — https://arxiv.org/abs/2502.09858
- **EviGraph** — https://arxiv.org/abs/2608.04738
- **Can LLM Agents Really Debate?** — https://arxiv.org/abs/2511.07784
- **Understanding Failure Modes in Multi-Agent Debate** — https://arxiv.org/abs/2509.05396
- **Autonomous Research Agents: Verification Gap** — https://arxiv.org/abs/2608.05179
- **XScientist** — https://arxiv.org/abs/2607.12301
- **W3C PROV-DM** — https://www.w3.org/TR/prov-dm/
- **W3C PROV-O** — https://www.w3.org/TR/prov-o/
