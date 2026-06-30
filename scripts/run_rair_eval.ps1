param(
    [string]$OutDir = "build/rair_eval",
    [string]$ManualPolicy = "scoring/routing_policy_manual.yaml"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Invoke-RairEval {
    param(
        [string]$DatasetName,
        [string]$DataPath,
        [string]$MethodLabel,
        [string]$Method,
        [string]$PolicyPath = ""
    )

    $outPath = Join-Path $OutDir "${DatasetName}_${MethodLabel}_predictions.jsonl"
    $summaryPath = Join-Path $OutDir "${DatasetName}_${MethodLabel}_summary.json"

    Write-Output "[rair-eval] dataset=$DatasetName method=$MethodLabel"
    if ($PolicyPath) {
        uv run python -m benchmarks.rair_rag.run_routing_eval `
            --data $DataPath `
            --method $Method `
            --policy $PolicyPath `
            --out $outPath `
            --summary $summaryPath
    }
    else {
        uv run python -m benchmarks.rair_rag.run_routing_eval `
            --data $DataPath `
            --method $Method `
            --out $outPath `
            --summary $summaryPath
    }
}

function Invoke-RairDataset {
    param(
        [string]$DatasetName,
        [string]$DataPath
    )

    Invoke-RairEval $DatasetName $DataPath "keyword-baseline" "keyword-baseline"
    Invoke-RairEval $DatasetName $DataPath "bert-multilabel" "bert-multilabel"
    Invoke-RairEval $DatasetName $DataPath "no-negation" "no-negation"
    Invoke-RairEval $DatasetName $DataPath "single-intent" "single-intent"
    Invoke-RairEval $DatasetName $DataPath "risk-router" "risk-router" $ManualPolicy
}

Invoke-RairDataset "rair_test" "benchmarks/rair_rag/data/test/rair_test.jsonl"
Invoke-RairDataset "rair_test_negation" "benchmarks/rair_rag/data/test/rair_test_negation.jsonl"
Invoke-RairDataset "rair_test_multi_intent" "benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl"
Invoke-RairDataset "rair_test_multi_intent_negation" "benchmarks/rair_rag/data/test/rair_test_multi_intent_negation.jsonl"

Write-Output "[rair-eval] done: $OutDir"
