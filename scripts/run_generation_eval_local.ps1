param(
    [string]$OutDir = "build/downstream_eval/generation/local",
    [string]$RagDb = $(if ($env:RAG_DB_PATH) { $env:RAG_DB_PATH } else { "build/rag.db" }),
    [int]$TopK = 3,
    [int]$MaxCases = 0,
    [switch]$IncludeExtension
)

$ErrorActionPreference = "Stop"

$args = @(
    "run",
    "python",
    "-m",
    "benchmarks.rair_rag.downstream.generation_matrix",
    "--generator",
    "local-llm",
    "--data",
    "benchmarks/rair_rag/data/test/rair_test.jsonl",
    "--rag-db",
    $RagDb,
    "--topk",
    $TopK,
    "--out-dir",
    $OutDir
)

if ($MaxCases -gt 0) {
    $args += @("--max-cases", $MaxCases)
}

if ($IncludeExtension) {
    $args += "--include-extension"
}

Write-Output "[generation-local] uv run python -m benchmarks.rair_rag.downstream.generation_matrix --generator local-llm"
& uv @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
