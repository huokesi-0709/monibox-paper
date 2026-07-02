param(
    [string]$OutDir = "build/downstream_eval/generation/reference",
    [string]$RagDb = $(if ($env:RAG_DB_PATH) { $env:RAG_DB_PATH } else { "build/rag.db" }),
    [int]$TopK = 3,
    [int]$MaxCases = 0,
    [switch]$IncludeExtension
)

$ErrorActionPreference = "Stop"

if (-not $env:REFERENCE_LLM_API_KEY) {
    [Console]::Error.WriteLine("[generation-reference] REFERENCE_LLM_API_KEY is not set. Set it in your environment or .env before running this script.")
    exit 2
}

if (-not $env:REFERENCE_LLM_PROVIDER) {
    $env:REFERENCE_LLM_PROVIDER = "dashscope_openai"
}

if (-not $env:REFERENCE_LLM_BASE_URL) {
    $env:REFERENCE_LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
}

if (-not $env:REFERENCE_LLM_MODEL) {
    $env:REFERENCE_LLM_MODEL = "qwen-plus"
}

$args = @(
    "run",
    "python",
    "-m",
    "benchmarks.rair_rag.downstream.generation_matrix",
    "--generator",
    "reference-llm",
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

Write-Output "[generation-reference] uv run python -m benchmarks.rair_rag.downstream.generation_matrix --generator reference-llm model=$env:REFERENCE_LLM_MODEL"
& uv @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
