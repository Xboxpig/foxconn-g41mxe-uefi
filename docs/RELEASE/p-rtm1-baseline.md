---
id: p-rtm1-baseline-release
role: RELEASE
status: current
proposal: p-rtm1-baseline
source-kind: proposal
merged-into: null
contracts:
- rtm-baseline
---

# G41MXE RTM1 交付契约

## 契约身份

rtm-baseline / g41mxe-x5450 / 1.0.0。

## 使用方可依赖

已认可镜像为 releases/g41mxe-rtm1/g41mxe-rtm1-16m.rom，SHA256
24567d0a88a38d6dc592263e169e177d9fdd39bda39b92a79e5fd25060e8aa83。
它保持用户实际使用的 v6 字节，用户确认真实主板启动与 ASUS UI 操作流畅并认可为 RTM。
完整兼容边界、已实现但未专项验收的功能见 docs/RELEASE/rtm1.md。
源码重建只能输出 build，不得覆盖此已认可版本。

## 部署与分发

v6 已经 CH341A 写入用户 W25Q128 并获得用户真实反馈；RTM1 归档没有再次刷写。
没有发布到公共渠道，也不表示 ASUS/Foxconn 官方支持或取得闭源资源分发许可。
任何内容变化后的新 ROM 必须以新身份验收，不冒称同一已认可 RTM。
