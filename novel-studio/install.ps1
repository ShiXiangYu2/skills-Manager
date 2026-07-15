# Novel Studio Skill 安装脚本
# 将技能安装到 Claude Code 的技能目录

$SKILL_NAME = "novel-studio"
$SKILL_SOURCE = $PSScriptRoot
$SKILL_TARGET = "$env:USERPROFILE\.claude\skills\$SKILL_NAME"

Write-Host "安装 Novel Studio 技能..." -ForegroundColor Cyan

# 创建目标目录
if (-not (Test-Path $SKILL_TARGET)) {
    New-Item -ItemType Directory -Path $SKILL_TARGET -Force | Out-Null
}

# 复制文件
Copy-Item -Path "$SKILL_SOURCE\*" -Destination $SKILL_TARGET -Recurse -Force

Write-Host "✓ 技能已安装到: $SKILL_TARGET" -ForegroundColor Green
Write-Host ""
Write-Host "使用方式:" -ForegroundColor Yellow
Write-Host "  1. 启动 novel-studio 后端: cd 'D:\GitHub Learn\novel-studio\backend' && python run.py" -ForegroundColor White
Write-Host "  2. 在 Claude Code 中输入 /novel-studio 启动技能" -ForegroundColor White
Write-Host ""
Write-Host "子技能:" -ForegroundColor Yellow
Write-Host "  /novel-pipeline    — 写作流水线" -ForegroundColor White
Write-Host "  /novel-techniques  — 技法库管理" -ForegroundColor White
Write-Host "  /novel-scoring     — 10维度评分" -ForegroundColor White
Write-Host "  /novel-retrospective — 写作复盘" -ForegroundColor White
