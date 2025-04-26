#!/bin/bash

# 定义路径（根据实际路径修改）
SOURCE_PATH="/mnt/f/1.中铁物贸成都分公司-四川物供中心/钢材-结算/钢筋发货计划-发丁小刚/发货计划（宜宾项目）汇总.xlsx"
TARGET_PATH="/mnt/f/GitHub/shipment-app/发货计划（宜宾项目）汇总.xlsx"
LOG_FILE="/mnt/f/GitHub/shipment-app/sync.log"
REPO_DIR="/mnt/f/GitHub/shipment-app"
BRANCH="main"

# 日志记录函数
log() {
    local message="$1"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S.%3N")
    echo "[$timestamp] - $message" >> "$LOG_FILE"
}

# 检查文件是否存在
check_source_file() {
    if [ ! -f "$SOURCE_PATH" ]; then
        log "❌ 错误：源文件不存在！"
        exit 1
    fi
}

# 关闭占用文件的进程（Linux 示例）
close_occupied_files() {
    # 使用 fuser 检测并终止占用文件的进程（需 root 权限）
    sudo fuser -k "$SOURCE_PATH" 2>/dev/null
    sudo fuser -k "$TARGET_PATH" 2>/dev/null
    log "✅ 尝试关闭占用文件的进程..."
}

# 复制文件（带重试）
copy_file() {
    local max_retries=3
    local retry_count=0
    while [ $retry_count -lt $max_retries ]; do
        if cp -f "$SOURCE_PATH" "$TARGET_PATH"; then
            log "✅ 文件复制成功！"
            return 0
        else
            retry_count=$((retry_count + 1))
            log "⚠️ 文件复制失败，第 $retry_count 次重试..."
            sleep 5
        fi
    done
    log "❌ 文件复制多次失败！"
    exit 1
}

# 验证文件哈希
verify_hash() {
    source_hash=$(sha256sum "$SOURCE_PATH" | awk '{print $1}')
    target_hash=$(sha256sum "$TARGET_PATH" | awk '{print $1}')
    if [ "$source_hash" == "$target_hash" ]; then
        log "✅ 文件哈希验证通过！"
    else
        log "❌ 文件哈希不一致，可能复制失败！"
        exit 1
    fi
}

# 配置 Git 编码（确保 UTF-8）
configure_git() {
    # 设置提交编码为 UTF-8
    git -C "$REPO_DIR" config --local i18n.commitencoding utf-8
    git -C "$REPO_DIR" config --local i18n.logoutputencoding utf-8
    log "✅ Git 编码配置完成！"
}

# 执行 Git 操作
git_commit() {
    cd "$REPO_DIR" || { log "❌ 进入仓库目录失败！"; exit 1; }

    # 添加文件到暂存区
    git add "$TARGET_PATH" &>> "$LOG_FILE"
    if [ $? -ne 0 ]; then
        log "❌ Git 添加文件失败！"
        exit 1
    fi

    # 提交更改（带时间戳信息）
    commit_message="自动同步发货计划文件 $(date +%Y%m%d)"
    git commit -m "$commit_message" &>> "$LOG_FILE"
    if [ $? -ne 0 ]; then
        log "❌ Git 提交失败！"
        exit 1
    fi

    # 推送到远程仓库
    git push origin "$BRANCH" &>> "$LOG_FILE"
    if [ $? -ne 0 ]; then
        log "❌ Git 推送失败！"
        exit 1
    fi
    log "✅ Git 提交并推送成功！"
}

# 主流程
main() {
    log "🚀 自动同步开始..."
    check_source_file
    close_occupied_files
    copy_file
    verify_hash
    configure_git
    git_commit
    log "🎉 自动同步完成！"
}

main