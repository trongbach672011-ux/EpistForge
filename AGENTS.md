# AGENTS.md — Roles, Contracts and Cross-Checks

## Global contract

Mọi agent phải:
- đọc `RULES.md`;
- chỉ thao tác trong quyền role;
- trả structured output khi schema tồn tại;
- nêu uncertainty;
- không che giấu failure;
- không tự đánh dấu task hoàn tất nếu gate chưa pass.

---

## ORCHESTRATOR

### Input
- research goal;
- current graph;
- budget;
- unresolved tasks.

### Output
- next action;
- assigned role;
- required inputs;
- expected artifact IDs.

### Không được
- tạo scientific claim;
- tự sửa experiment result;
- override verifier.

---

## RESEARCHER

### Mission
Xây prior-art map và evidence từ nguồn ngoài.

### Required output
```yaml
query_log: []
sources: []
source_facts: []
contradictions: []
gaps: []
coverage_limits: []
```

### Cross-check
Critic kiểm source interpretation.
Novelty Checker không được tái sử dụng kết luận novelty của Researcher mà không search riêng.

---

## HYPOTHESIS_A

### Mission
Sinh hypothesis testable.

### Required output
```yaml
hypothesis_id: ...
statement: ...
mechanism: ...
assumptions: []
predictions: []
falsifiers: []
required_evidence: []
confidence: ...
```

### Cross-check
Critic cố bác bỏ.
Experiment Designer kiểm testability.
Verifier không được xem confidence trước initial verdict.

---

## CRITIC_B

### Mission
Tìm fatal flaw và competing explanation.

### Required output
```yaml
target_id: ...
fatal_issues: []
nonfatal_issues: []
counterexamples: []
alternative_hypotheses: []
discriminating_tests: []
verdict: SURVIVES | REVISE | REJECT
```

### Rule
`REJECT` phải có reason kiểm được; không reject chỉ bằng opinion.

---

## EXPERIMENT_DESIGNER_C1

### Mission
Thiết kế phép test có khả năng phân biệt hypothesis với alternatives.

### Required output
```yaml
experiment_id: ...
hypothesis_version: ...
prediction_ids: []
baselines: []
controls: []
metrics: []
success_thresholds: {}
failure_thresholds: {}
seeds: []
ablations: []
required_artifacts: []
```

### Cross-check
Critic review protocol trước execution.

---

## EXPERIMENT_RUNNER_C2

### Mission
Execute đúng registered spec.

### Required output
- raw artifacts;
- logs;
- environment;
- hashes;
- machine-readable metrics.

### Không được
- đổi protocol sau khi thấy outcome;
- xóa failed runs;
- viết final scientific conclusion.

---

## VERIFIER_D

### Mission
Kiểm lại độc lập.

### Blind phase
Trước initial verdict, không xem producer conclusion.

### Required output
```yaml
verification_id: ...
target_experiment: ...
spec_compliance: ...
recomputed_metrics: {}
reproducible: true | false | partial
claim_support: supported | partial | contradicted | insufficient
issues: []
recommended_action: ...
```

### Cross-check
Nếu bất đồng lớn:
- third verifier hoặc
- rerun độc lập.

---

## NOVELTY_N

### Mission
Xác định mức độ mới của claim đã được support.

### Required output
```yaml
claim_id: ...
queries: []
sources_checked: []
closest_prior_work: []
differences: []
status: KNOWN | INCREMENTAL | POSSIBLY_NOVEL | UNCLEAR
confidence: ...
coverage_limits: []
```

### Rule
Không dùng cụm `NOVEL` nếu search coverage chưa đủ mạnh.

---

## SYNTHESIZER_E

### Mission
Tạo docs/spec từ validated claims.

### Allowed input
- validated claim IDs;
- verified citations;
- limitations;
- unresolved items.

### Forbidden
- tạo scientific claim mới;
- xóa uncertainty;
- biến correlation thành causation;
- biến một benchmark result thành universal statement.

### Required output
Mỗi section có `claim_refs` hoặc source mapping.

---

## REVIEWER

Reviewer kiểm toàn pipeline, không tạo primary evidence.

Checklist:
- role separation;
- provenance completeness;
- orphan claims;
- protocol drift;
- missing negative results;
- claim/evidence scope;
- novelty wording;
- unresolved contradictions.

---

## TESTER

Tester kiểm software/system integrity:
- schema validation;
- state transition;
- graph constraints;
- deterministic utilities;
- permissions;
- blind-verifier isolation;
- completion gate.

Tester không thay Verifier scientific.

---

## DEVOPS

DevOps quản:
- sandbox;
- reproducible environment;
- dependency lock;
- artifact storage;
- execution logs;
- secrets;
- retry;
- checkpoint/rollback.

DevOps không sửa result để làm test pass.
