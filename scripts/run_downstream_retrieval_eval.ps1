param(
    [string]$OutDir = "build/downstream_eval/retrieval",
    [string]$RagDb = $(if ($env:RAG_DB_PATH) { $env:RAG_DB_PATH } else { "build/rag.db" }),
    [int]$TopK = 3
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $RagDb)) {
    [Console]::Error.WriteLine("[downstream-retrieval] RAG database not found: $RagDb. Please run 'uv run monibox-build-rag' first, or pass -RagDb / set RAG_DB_PATH.")
    exit 2
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Invoke-DownstreamRetrievalEval {
    param(
        [string]$DatasetName,
        [string]$DataPath,
        [string]$System
    )

    $outPath = Join-Path $OutDir "${DatasetName}_${System}_predictions.jsonl"
    $summaryPath = Join-Path $OutDir "${DatasetName}_${System}_summary.json"

    Write-Output "[downstream-retrieval] dataset=$DatasetName system=$System topk=$TopK"
    uv run python -m benchmarks.rair_rag.downstream.retrieval_eval `
        --data $DataPath `
        --system $System `
        --rag-db $RagDb `
        --topk $TopK `
        --out $outPath `
        --summary $summaryPath
}

function Invoke-DownstreamRetrievalDataset {
    param(
        [string]$DatasetName,
        [string]$DataPath
    )

    Invoke-DownstreamRetrievalEval $DatasetName $DataPath "vanilla-rag"
    Invoke-DownstreamRetrievalEval $DatasetName $DataPath "keyword-rag"
    Invoke-DownstreamRetrievalEval $DatasetName $DataPath "bert-rag"
    Invoke-DownstreamRetrievalEval $DatasetName $DataPath "rair-rag"
}

Invoke-DownstreamRetrievalDataset "rair_test" "benchmarks/rair_rag/data/test/rair_test.jsonl"
Invoke-DownstreamRetrievalDataset "rair_test_multi_intent_negation" "benchmarks/rair_rag/data/test/rair_test_multi_intent_negation.jsonl"

Write-Output "[downstream-retrieval] done: $OutDir"
