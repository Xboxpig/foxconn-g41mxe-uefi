# Foxconn G41MXE RTM1

适用 Foxconn G41MXE rev1.0、G41 + ICH7、IT8720F、771 改装 Xeon X5450、W25Q128 16 MiB。
基于 coreboot + EDK II，保留真实 ASUS/AMI 图形界面、本板传感器 provider 和设置 consumer。

此 ROM 是用户真机验证并认可的 v6 原样归档，未重新编译或改变字节。

- 文件：g41mxe-rtm1-16m.rom，16,777,216 bytes。
- SHA256：24567d0a88a38d6dc592263e169e177d9fdd39bda39b92a79e5fd25060e8aa83。
- 默认关闭 CSM；无可用 UEFI OS 项时进入 ASUS UI。Shell/iPXE 为手动工具。
- 已认可范围：真实主板启动、进入 ASUS UI 与操作流畅；不是所有设置的专项硬件验收。
- 原生 CSM 通过 Q35 MBR/INT10/INT13/PIC 路径；真机 Legacy 磁盘、独显、Legacy USB/PXE、
  变量跨重启持久化及每种风扇预设仍需专项验证。

仅适用于这块已确认的主板，不能刷到 donor Z490 或其他 G41 主板。
整片刷写会重置启动项和设置；刷写前请准备可恢复的原 BIOS 备份和外置编程器。
ASUS/AMI donor、资源和 Logo 是闭源二进制，公开上传不代表重新授权、官方支持或取得厂商许可。

源码、patch/overlay、构建和回归入口及29篇技术细节均在同一仓库；本机硬件备份、凭据、
Python环境、编译器和构建缓存不随仓库发布。完整范围见根 README、docs/LICENSING.md 和 RTM 契约。
