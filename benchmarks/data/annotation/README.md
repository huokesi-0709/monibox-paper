# Annotation Workspace

This folder stores templates for building the formal SCI paper dataset.

- `clean_candidates_template.csv`: draft clean inputs before annotation.
- `annotator_template.csv`: copy this file once for each annotator, for example `annotator_a.csv` and `annotator_b.csv`.

Do not treat the template rows as the final dataset. Expand and review them before paper reporting.

Generated starter files:

- `clean_candidates_seed.csv`
- `annotator_a_seed.csv`
- `annotator_b_seed.csv`

These files were exported from the current 10 clean development cases. Open them in a UTF-8 aware editor or spreadsheet program. If PowerShell prints Chinese text as garbled characters, that is a terminal encoding issue rather than a CSV structure problem.

## Formal Candidate Generation

Use this command to build the formal clean candidate pool:

```bash
python -m benchmarks.build_clean_candidates --out benchmarks/data/annotation/clean_candidates.csv
```

Then prepare independent annotator sheets:

```bash
python -m benchmarks.prepare_annotation_sheets --candidates benchmarks/data/annotation/clean_candidates.csv --annotator-a-out benchmarks/data/annotation/annotator_a.csv --annotator-b-out benchmarks/data/annotation/annotator_b.csv
```

For long sheets, split each annotator file into smaller batches before sending it to LLM annotators:

```bash
python -m benchmarks.split_annotation_sheet --input benchmarks/data/annotation/annotator_a.csv --output-dir benchmarks/data/annotation/batches/a --batch-size 50
python -m benchmarks.split_annotation_sheet --input benchmarks/data/annotation/annotator_b.csv --output-dir benchmarks/data/annotation/batches/b --batch-size 50
```

After annotators return all batches, merge them back:

```bash
python -m benchmarks.merge_annotation_batches --input-dir benchmarks/data/annotation/batches/a --out benchmarks/data/annotation/annotator_a.csv
python -m benchmarks.merge_annotation_batches --input-dir benchmarks/data/annotation/batches/b --out benchmarks/data/annotation/annotator_b.csv
```

Then compute agreement and build adjudication batches:

```bash
python -m benchmarks.annotation_agreement --annotator-a benchmarks/data/annotation/annotator_a.csv --annotator-b benchmarks/data/annotation/annotator_b.csv --out-json build/eval/annotation/agreement_formal.json --out-csv build/eval/annotation/agreement_formal.csv
python -m benchmarks.build_adjudication_batches --annotator-a benchmarks/data/annotation/annotator_a.csv --annotator-b benchmarks/data/annotation/annotator_b.csv --output-dir benchmarks/data/annotation/adjudication_batches --batch-size 50
```

The generated `clean_candidates.csv` is a scenario-written candidate pool. It is not a final benchmark until it has passed independent annotation, inter-annotator agreement checks, adjudication, and author verification.

## LLM-Assisted Annotation Disclosure

For the paper, describe the workflow transparently as LLM-assisted annotation, not as human expert double annotation:

> We adopted an LLM-assisted dual-annotation workflow. Two independent LLM annotators labeled risk level, primary intent, route, protocol ID, unsafe actions, and reference replies. Inter-annotator agreement was measured before adjudication. Disagreements were resolved by a third adjudication model and manually checked by the authors. The final labels were used to construct the dev/test benchmark splits.

Recommended Chinese note:

> 本研究采用 LLM 辅助双标注流程。两个独立 LLM 标注员分别标注风险等级、主意图、路由、协议 ID、危险动作和参考回复；在裁决前计算标注一致性；分歧由第三个裁决模型解决，并由作者进行人工核查。最终标签用于构建 dev/test benchmark。

This disclosure is acceptable for a scenario-based benchmark if the paper clearly reports the workflow, agreement statistics, adjudication, and author verification. Do not claim that the labels were produced by human clinical or emergency experts unless such experts actually participated.
