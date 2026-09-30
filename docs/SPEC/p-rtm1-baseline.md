---
id: p-rtm1-baseline-spec
role: SPEC
status: current
proposal: p-rtm1-baseline
source-kind: proposal
merged-into: null
contracts:
- rtm-baseline
---

# G41MXE RTM1 镜像基线

## 契约身份

rtm-baseline / g41mxe-x5450 / 1.0.0。适用 Foxconn G41MXE rev1.0、X5450、W25Q128 16 MiB。

## 可依赖行为

归档并保持用户刚验证的 v6 镜像，文件为 releases/g41mxe-rtm1/g41mxe-rtm1-16m.rom。
容量 16,777,216 bytes，SHA256 24567d0a88a38d6dc592263e169e177d9fdd39bda39b92a79e5fd25060e8aa83。
RTM1 只改归档名称，不更改字节、不额外刷写。用户在真实主板启动并认可 UI 流畅性后指定其为 RTM。
源码目录重排和新编译输出不自动继承这一认可。

## 验收场景

user-rtm-e2e：用户已将上述镜像装回 G41MXE，实际启动、进入和操作 ASUS UI，
明确反馈“这一版非常流畅，我认为可以作为RTM”。该反馈与上一轮写入的 v6 身份绑定。
本次以 ROM SHA256 和归档 verifier 核对身份保持，不能用 QEMU 替代这次真实反馈。

## 不覆盖

这不是对所有设置、真机 Legacy 磁盘/INT10/变量跨 reset 持久化、独显、Legacy USB/PXE
或具体旧 OS 的独立验收。完整手动超频、Secure Boot 和公共分发许可不在契约内。
技术清单与限制见 docs/RELEASE/rtm1.md，未验证事项继续保留，不因 RTM 名称而自动成功。
