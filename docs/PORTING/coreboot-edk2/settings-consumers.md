# 设置项 schema、默认值与硬件 consumer

## 原生字段顺序

g41_native_settings.json的顺序就是G41PlatformData slot；不要独立调整生成头或UI顺序。
所有存储为coreboot NV GUID下的UINT32，允许值由schema mask验证。

| slot/name | 默认/允许 | consumer |
| --- | --- | --- |
| 0 eist |1，0/1|model_1067x P-state初始化|
| 1 vmx |1，0/1|model_1067x MP/VMX初始化|
| 2 gfx_uma_size |6，6..12离散代码|G41 GGC stolen memory|
| 3 sata_mode |2，1/2|ICH7 IDE Legacy Combined / Native|
| 4 pata_controller |1，0/1|ICH7 PATA enable|
| 5 hd_audio |1，0/1|ICH7 HDA enable|
| 6 onboard_lan |1，0/1|连接RTL8168/8111的PCIe端口|
| 7 power_on_after_fail |0，0/1|ICH7电源恢复策略|
| 8 post_success_beep |1，0/1|coreboot payload handoff短音|
| 9 nmi |0，0/1|ICH7 NMI策略|
| 10 memory_fast_boot |1，0/1|x4x缓存/完整training|
| 11 csm_enable |0，0/1|EDK本次boot平台服务|
| 12 boot_device_control |0，0/1/2|Boot Manager启动架构过滤|

## 按 consumer 分开的详细记录

- [CPU EIST/VMX 与锁定时机](cpu-policy.md)
- [内存 cap、MRC cache 身份和完整训练](memory-training.md)
- [UMA、ICH7 外设、恢复电源与 beep](chipset-policy.md)
- [独立 QFan / IT8720F 控制预设](../it8720f/fan-control.md)
- [CSM 服务与启动策略](../native-csm/platform-policy.md)

## UMA 和训练

UMA代码6/7/8/9/10/11/12对应64/128/256/96/160/224/352MiB；并非简单步进enum。
memory_fast_boot=0在warm reboot先cold reset再完整training；S3不能丢弃原训练。
SaSetup的rate cap是另外一条历史桥接路径，不是同一个native slot。
改变SATA IDE模式可能让已装系统不能启动，不能当作无风险UI偏好。

## 实现与验收

板级patch负责将本地option连接CPU/x4x/ICH7/IT8720F；默认fallback保留硬件安全策略。
POST beep需要接主板speaker，屏幕自检成功不能让没有speaker的硬件发声。
schema/ConfigAccess/consumer源码已验证，但具体每个设置的真机效果不因RTM认可全部成立。
无AHCI/RAID、VT-d、DDR4/XMP、手工PLL/FSB/电压/时序，不能仅为了菜单丰富加空开关。

源码 / 回归入口：[g41_native_settings.json](../../../src/boards/foxconn-g41mxe/asus-ui/g41_native_settings.json) / [g41_csm_settings.json](../../../src/boards/foxconn-g41mxe/asus-ui/g41_csm_settings.json) / [G41NativeOptions.h](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusSetupHiiDxe/G41NativeOptions.h)。
