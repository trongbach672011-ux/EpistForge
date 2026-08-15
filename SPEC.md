# SPEC.md — Multi-Agent Knowledge Discovery Protocol v0.1

## 1. Source of truth

Source of truth là **Evidence Graph + immutable artifacts**, không phải chat transcript.

Transcript chỉ phục vụ debugging/audit.

---

## 2. Core entities

### Hypothesis

```json
{
  "id": "H-001",
  "version": 1,
  "statement": "...",
  "mechanism": "...",
  "assumptions": [],
  "predictions": ["P-001"],
  "falsifiers": ["F-001"],
  "required_evidence": [],
  "created_by": "A1",
  "status": "HYPOTHESIS"
}
```

### Experiment

```json
{
  "id": "EXP-001",
  "hypothesis_id": "H-001",
  "hypothesis_version": 1,
  "registered_before_run": true,
  "baselines": [],
  "controls": [],
  "metrics": [],
  "success_thresholds": {},
  "failure_thresholds": {},
  "seeds": [],
  "ablations": [],
  "revision": 0
}
```

### Artifact

```json
{
  "id": "ART-001",
  "type": "raw_result",
  "created_by": "C2",
  "input_ids": [],
  "tool": "...",
  "tool_version": "...",
  "config_hash": "...",
  "content_hash": "...",
  "path": "..."
}
```

### Evidence

```json
{
  "id": "E-001",
  "finding_id": "FIND-001",
  "artifact_ids": ["ART-001"],
  "direction": "SUPPORTS",
  "strength": "MODERATE",
  "conditions": []
}
```

### Claim

```json
{
  "id": "C-001",
  "text": "...",
  "scope": {},
  "evidence_ids": ["E-001"],
  "verification_ids": [],
  "status": "SUPPORTED"
}
```

### Verification

```json
{
  "id": "V-001",
  "experiment_id": "EXP-001",
  "verifier": "D1",
  "blind_initial_verdict": true,
  "recomputed_metrics": {},
  "issues": [],
  "verdict": "SUPPORTED"
}
```

---

## 3. State machine

Allowed transitions:

```text
IDEA -> HYPOTHESIS
HYPOTHESIS -> CRITIQUED
CRITIQUED -> TESTABLE
CRITIQUED -> REJECTED
TESTABLE -> EXPERIMENT_REGISTERED
EXPERIMENT_REGISTERED -> EXECUTED
EXECUTED -> SUPPORTED
EXECUTED -> REFUTED
EXECUTED -> INCONCLUSIVE
SUPPORTED -> VERIFIED
SUPPORTED -> DISPUTED
VERIFIED -> NOVELTY_CHECKED
VERIFIED -> PROVISIONAL_KNOWLEDGE
NOVELTY_CHECKED -> PROVISIONAL_KNOWLEDGE
PROVISIONAL_KNOWLEDGE -> DISPUTED
DISPUTED -> RETRACTED
DISPUTED -> VERIFIED
```

Mọi transition ngoài danh sách phải fail validation.

---

## 4. Gate definitions

### Hypothesis Gate

Pass nếu:
- mechanism không rỗng;
- có >= 1 prediction;
- có >= 1 falsifier;
- assumptions được ghi;
- không có fatal critique chưa giải quyết.

### Experiment Gate

Pass nếu:
- protocol registered trước run;
- baseline/control có lý do;
- metric + threshold có trước outcome;
- expected artifacts được khai báo.

### Evidence Gate

Pass nếu:
- artifact tồn tại;
- artifact hash hợp lệ;
- finding có nguồn;
- evidence chỉ claim điều artifact support.

### Verification Gate

Pass nếu:
- independent role;
- blind initial verdict;
- recompute hoặc giải thích vì sao không thể;
- spec compliance được kiểm;
- issue P0 không tồn tại.

### Novelty Gate

Pass nếu:
- query log tồn tại;
- closest prior work tồn tại hoặc ghi rõ không tìm thấy;
- coverage limitations được nêu;
- wording không mạnh hơn mức search.

### Writing Gate

Pass nếu:
- mỗi major claim có valid claim ID;
- không có orphan claim;
- limitations có mặt;
- disputed claim được đánh dấu;
- writer không tạo new claim.

---

## 5. Agent message contract

Agent giao tiếp qua object thay vì prose tự do khi có thể.

Envelope:

```json
{
  "task_id": "T-...",
  "agent_id": "...",
  "role": "...",
  "input_refs": [],
  "output_refs": [],
  "status": "SUCCESS|PARTIAL|FAILED|BLOCKED",
  "uncertainties": [],
  "next_actions": []
}
```

Không truyền full transcript nếu không cần.

---

## 6. Conflict resolution

Nếu agents bất đồng:

```text
opinion vs opinion
=> chưa giải quyết

opinion vs evidence
=> evidence ưu tiên nếu evidence hợp lệ

evidence vs evidence
=> mark DISPUTED + design discriminating experiment

verifier vs producer
=> no promotion + rerun/third verifier
```

---

## 7. Provenance

Mỗi derived object phải có lineage.

Khái niệm tương thích tinh thần W3C PROV:

```text
Agent
  |
associated_with
  v
Activity
  |
generated
  v
Entity
  |
derived_from
  v
Entity
```

Fields tối thiểu:
- ID;
- creator;
- timestamp;
- inputs;
- tool/model/version;
- config;
- hashes.

---

## 8. Reproducibility

Mỗi experiment nên có:

```text
run.sh / run.py
locked dependencies
environment metadata
seed
dataset identifier/hash
config
raw output
metric recomputation script
```

Một người/agent mới phải có thể hiểu:
1. chạy cái gì;
2. input nào;
3. command nào;
4. output mong đợi ở đâu;
5. metric tính thế nào.

---

## 9. Research memory

Không lưu một summary duy nhất.

Memory chia thành:

```text
facts/
hypotheses/
refutations/
experiments/
evidence/
claims/
contradictions/
lessons/
```

Prior claim bị bác bỏ không bị delete; đổi state.

---

## 10. Final knowledge format

Ví dụ:

```yaml
claim_id: C-018
statement: >
  Trong benchmark X, cấu hình Y, method M cải thiện metric Z
  so với baseline B trong các điều kiện đã test.
status: PROVISIONAL_KNOWLEDGE
scope:
  benchmark: X
  model: Y
evidence:
  - E-031
verification:
  - V-009
novelty:
  status: POSSIBLY_NOVEL
limitations:
  - Chưa test ngoài benchmark X.
```

---

## 11. Anti-patterns bị cấm

```text
A proposes -> B agrees -> C summarizes -> "new knowledge"
```

```text
5 agents vote yes -> verified
```

```text
experiment failed -> delete run -> retry until success
```

```text
writer adds a plausible explanation without claim ID
```

```text
search didn't find it -> definitely novel
```

```text
one successful seed -> universal conclusion
```

---

## 12. MVP success criteria

MVP đạt khi:

- 3 hypothesis agents chạy độc lập;
- 2 critic roles;
- 1 experiment designer + runner;
- 1 blind verifier;
- evidence graph validation;
- claim promotion gate;
- novelty report;
- final docs generated only from validated claims;
- failed runs retained;
- test suite kiểm được hard rules.

---

## 13. References

- https://arxiv.org/abs/2502.18864
- https://arxiv.org/abs/2502.09858
- https://arxiv.org/abs/2608.04738
- https://arxiv.org/abs/2511.07784
- https://arxiv.org/abs/2509.05396
- https://arxiv.org/abs/2608.05179
- https://arxiv.org/abs/2607.12301
- https://www.w3.org/TR/prov-dm/
- https://www.w3.org/TR/prov-o/
