---
id: p-rtm1-baseline-dev
role: DEV
status: history
proposal: p-rtm1-baseline
source-kind: proposal
merged-into: null
---

# RTM1 基线登记记录

## 范围与决定

用户在 v6 写入后的下一条反馈“这一版非常流畅，我认为可以作为RTM”，同时明确要求
使用 harness skill 整理记录、源码和工作目录。此登记只覆盖已认可的原样镜像，不新增固件行为。
本板 Legacy 等尚未验收边界明确保留。源码重排由单独的开发验证检查，不套用 UI 验收。

## 已有与本次证据

上一轮 flashrom 在 CH341A/W25Q128.V 写入 v6，exit 0；没有写后验证。
用户随后在真机反馈流畅并认可为 RTM。本次归档 SHA256 与写入版本一致。
tools/test.sh 已在拆分布局通过：HII/PE/hash 边界、CSM policy、1536 mode 转换、
sensor mock fixture、14 项 fan/memory policy、56 项实际 ConfigAccess 与完整 RTM verifier。
旧目录的 39 个 coreboot 修改/新增文件、200 个 EDK 修改/新增文件与重新组合结果一致
（比较允许历史 CRLF/LF 差异）。所有原始本地改动保存在 patch/overlay，未 git reset 或 checkout。
构建/清理的完整交付说明见根 README 和 releases/g41mxe-rtm1/evidence/validation.md。
