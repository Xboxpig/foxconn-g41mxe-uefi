# G41MXE RTM1：已认可镜像与验收边界

## 交付身份

RTM1 是此前 `g41mxe-asus-native-csm-v6-16m-CANDIDATE.rom` 的字节相同归档。
文件：`releases/g41mxe-rtm1/g41mxe-rtm1-16m.rom`；16,777,216 bytes。
SHA256：`24567d0a88a38d6dc592263e169e177d9fdd39bda39b92a79e5fd25060e8aa83`。
适用 G41MXE rev1.0 / G41 + ICH7 / IT8720F / Xeon X5450 / W25Q128 16 MiB。

## 用户认可

来源是本会话在 v6 写入完成后的用户反馈：
“这一版非常流畅，我认为可以作为RTM”。本版曾由 CH341A 写入 W25Q128，flashrom exit 0；
按用户要求没有单独整片清零、备份或写后回读验证。后续用户在主板上启动确认流畅。
这一认可绑定上述镜像身份及真实启动/UI 响应，不能移用到内容变化的重建 ROM。

## 使用方可以依赖的范围

此镜像作为已认可的本板 RTM 基线保存，保留快速 UEFI Setup、ASUS UI、本地传感器 provider、
G41 设置 consumer、UEFI iPXE 和默认关闭的原生 CSM 代码。源码和资料整理不更改其字节。
没有默认可用 UEFI 项时进入 ASUS UI；设置保存后按相应 consumer 的重启规则应用。
技术实现清单不构成每个控制项的独立硬件验收。

## 明确未验收

CSM 的真实 Legacy 磁盘/GMA INT10/设置跨重启持久化、独显、Legacy USB/PXE、具体旧 OS 和
全部设置/风扇预设效果，不属于这次“UI 流畅”反馈的专项验收范围。
没有 Secure Boot、手动 PLL/FSB、电压或时序超频，也不承诺厂商完整 UEFI 的全设备兼容性。

## 部署与发布

该版本已写入用户芯片并收到真机反馈；RTM1 文件只是归档改名，没有再次刷写。
没有创建公共 release、上传外部仓库或获得 ASUS/Foxconn 的公开分发许可。
未来 ROM 内容变化需重新构建、校验和真实验收；不可覆盖本文件的镜像身份冒充同一 RTM。

