#!/bin/bash
# 钢材发货计划SSH自动推送脚本

REPO_DIR="/f/GitHub/shipment-app"
LOG_FILE="$REPO_DIR/push.log"

exec >> "$LOG_FILE" 2>&1  # 记录所有输出到日志

echo "===== 开始推送流程 [$(date +'%Y-%m-%d %H:%M:%S')] ====="

cd "$REPO_DIR" || exit 1

# 关闭可能占用文件的Excel进程（Windows环境）
taskkill //F //IM EXCEL.EXE 2>/dev/null
sleep 1

# 同步文件（根据实际路径修改）
cp -f "/f/1.中铁物贸成都分公司-四川物供中心/钢材-结算/钢筋发货计划-发丁小刚/发货计划（宜宾项目）汇总.xlsx" .

# Git操作
git add .
git commit -m "自动推送: $(date +'%Y-%m-%d %H:%M:%S')"

# 智能冲突处理
if ! git pull --rebase origin main; then
    echo "检测到冲突，采用远程版本..."
    git checkout --ours -- .
    git add -A
    git rebase --continue
fi

# 最终推送
if git push origin main; then
    echo "✅ 推送成功"
else
    echo "❌ 推送失败，错误代码：$?"
fi

echo "===== 流程结束 [$(date +'%Y-%m-%d %H:%M:%S')] ====="