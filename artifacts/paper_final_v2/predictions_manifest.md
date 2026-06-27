# final_v2 predictions manifest

Large prediction JSONL files are not duplicated in `artifacts/paper_final_v2/`.
They remain under `build/eval/final_v2/` and can be regenerated with the final_v2 scripts.

| Suite | File | Samples | Bytes | SHA256 |
| --- | --- | ---: | ---: | --- |
| clean | `build/eval/final_v2/clean/hsc-rag-de_predictions.jsonl` | 1000 | 7886429 | `ef3c7737158e820efad708bbf5b76c3ea2c0cb3256ed9f47b9847eb0fb03d407` |
| clean | `build/eval/final_v2/clean/hsc-rag-manual_predictions.jsonl` | 1000 | 7817793 | `3258a023508e16357755539800dcc0e700fc1dba61d0f3ecea5ebd0568010421` |
| clean | `build/eval/final_v2/clean/rag-guard_predictions.jsonl` | 1000 | 7763342 | `4df6305081190b46725efb7ec84c73557960c4e8432c4a0d36eb1056f11d8349` |
| clean | `build/eval/final_v2/clean/vanilla-rag_predictions.jsonl` | 1000 | 7785322 | `e3c34578a34d1640cb2794c99243e732c887fc63424eef304b011dd4acb167cd` |
| robust | `build/eval/final_v2/robust/hsc-rag-de_predictions.jsonl` | 3000 | 25636679 | `2bf58fbfff7acb6bac2b562a0afa5d7c29ab22c9613dc11819405f12ee2ceb14` |
| robust | `build/eval/final_v2/robust/hsc-rag-manual_predictions.jsonl` | 3000 | 25445952 | `5b806588fa881cceb0caffa1fe5623f58709e734c380a5fbeb1d98ec05001618` |
| robust | `build/eval/final_v2/robust/rag-guard_predictions.jsonl` | 3000 | 25157374 | `5c9b36343ae84ad827484187135cdf2ed3024d125cc6ca8a28134e3aa6098a3d` |
| robust | `build/eval/final_v2/robust/vanilla-rag_predictions.jsonl` | 3000 | 25223370 | `171a748443107b7be4834b6da4abb33571e906e2febbfa4057d391d56e6c023a` |
| ablation | `build/eval/final_v2/ablation/without_de_optimization_predictions.jsonl` | 3000 | 25665068 | `de1220a79f3e02ae428f4eaacd0a0b9aa6bd5ad73d92728e06f798615b9d8de2` |
| ablation | `build/eval/final_v2/ablation/without_guard_predictions.jsonl` | 3000 | 25789809 | `3b1efd8a3b4b9f5ddc5d5eb16654193f505ddf1648fc05c91a18f46ad689449d` |
| ablation | `build/eval/final_v2/ablation/without_input_normalization_predictions.jsonl` | 3000 | 26345850 | `a12cc79548c69efdee02efee836fe1d99337512180b12372973f0169d149fc0c` |
| ablation | `build/eval/final_v2/ablation/without_low_evidence_predictions.jsonl` | 3000 | 26009694 | `b03d13941c1583f786cc053d5245fddd1c3464cd1318e8d88bf57fe63bc7c89b` |
| ablation | `build/eval/final_v2/ablation/without_multi_intent_predictions.jsonl` | 3000 | 25670533 | `29c118675217f3759e4b7cf923634a6ad19c67ddbadafbee9125fb2cb415bef4` |
| ablation | `build/eval/final_v2/ablation/without_negation_predictions.jsonl` | 3000 | 25962030 | `07dfbcf4a489a7789d7b2cca3efda92ad4da73829765196163d9fa5f82c5fffa` |
| ablation | `build/eval/final_v2/ablation/without_protocol_gate_predictions.jsonl` | 3000 | 25803308 | `fdde3abcbaf0c7b1845672c73af86d11a6dc3c5d44e6ea74d1be9879684c3f4a` |
| ablation | `build/eval/final_v2/ablation/without_safety_rerank_predictions.jsonl` | 3000 | 25933572 | `6ea24763788cc36ab88e9076997fdbd2dd56296bc71df76533f616ff10dd9a60` |

## Regeneration

Use Git Bash on this Windows workspace:

```powershell
& "D:\app\Git\Git\bin\bash.exe" scripts/run_final_v2_all.sh
```
