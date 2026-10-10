# 安装依赖（兼容本机代理异常环境）
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .\.venv)) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip --proxy=""
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt --proxy="" `
  -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

if (-not (Test-Path .\.env)) {
    Copy-Item .\.env.example .\.env
    Write-Host "已创建 .env，请按需填写 OPENAI_API_KEY"
}

Write-Host "安装完成。可运行: python cli.py  或  streamlit run streamlit_app.py"
