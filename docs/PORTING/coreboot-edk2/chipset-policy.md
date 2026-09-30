# G41 / ICH7 设备、UMA、电源和 POST beep

## GGC stolen memory

gfx_uma_size 是 GGC 编码，不是 MiB 数字直接写寄存器：
6/7/8/9/10/11/12 分别为 64/128/256/96/160/224/352 MiB，默认6。
consumer 在 x4x 初始化中读取并形成保留区；CFR 和 ASUS schema 必须采用相同离散编码。
改变设置后重启，不能将界面当前值当作已经改变正在运行的 framebuffer。
显示链依赖 libgfxinit、板级 VBT 和 GMA 输出配置；它不是 ASUS donor 的 Z490 GOP。

## ICH7 与板载设备

| 设置 | 实际对象 / 行为 |
| --- | --- |
| hd_audio | root PCI 00:1b.0 enable |
| onboard_lan | root PCI 00:1c.1，RTL8168/8111 所在 PCIe bridge |
| pata_controller | root PCI 00:1f.1 PATA enable |
| sata_mode=1 | IDE Legacy Combined |
| sata_mode=2 | IDE Native，默认 |
| power_on_after_fail | ICH7 LPC 电源恢复配置，默认0 |
| nmi | ICH7 LPC NMI policy，默认0 |

board mainboard.c 调整 dev->enabled；不是靠 UI 隐藏 PCI 名称禁用设备。
SATA 只开放上述 IDE 模式，本 ICH7 没有本项目可用的 AHCI/RAID。
切模式可能改变已装系统的驱动要求，必须提示重启和启动风险。
关闭 LAN bridge 同时会影响 iPXE 可用性；UEFI 网络入口存在不代表网卡仍开启。
串口、并口、软驱等有本地 consumer，不表示当前 ASUS allowlist 把所有 CFR 控件都展示了。

## 短音的精确定义

[post_success_beep.c](../../../src/boards/foxconn-g41mxe/coreboot-overlay/src/mainboard/foxconn/g41s-k/post_success_beep.c)
在 BS_PAYLOAD_BOOT / BS_ON_ENTRY 执行；post_success_beep 默认1。
PIT channel2 用端口42/43、command b6，输入1193180Hz / 1000Hz divisor，180ms；
先保存端口61，开启低2bit，结束恢复端口61。
这证明 coreboot 已到 payload handoff，不是所有 DXE、启动介质或 OS 均自检通过。
需要实际 SPEAKER header 的 passive speaker；CPU_FAN、屏幕和声卡不能替代它。

## 入口与验收

板级 mainboard.c、variant overridetree.cb 及 coreboot.patch 保存这些 consumer；
[settings 表](settings-consumers.md)保存变量名/默认值，ConfigAccess 回归保存值域约束。
独立构建与 RTM 启动已经验证；每个外设开关、电源状态和不同 UMA 配置仍需专门真机验证。

源码 / 回归入口：[mainboard.c](../../../src/boards/foxconn-g41mxe/coreboot-overlay/src/mainboard/foxconn/g41s-k/mainboard.c) / [cfr.h](../../../src/boards/foxconn-g41mxe/coreboot-overlay/src/northbridge/intel/x4x/cfr.h)。
