# coreboot + EDK II：技术导航

coreboot 负责 G41/ICH7/内存/IT8720F 初始化，EDK II 提供 UEFI 服务、Boot Manager、GOP/HII 和 ASUS UI。
本板硬件代码与两个上游快照分离，只有生成的 build 树进行组合。

- [16 MiB SPI 布局、CBFS/payload、MRC 与 SMMSTORE](coreboot-edk2/flash-map-variables.md)
- [13 个 native setting 的 slot/default/consumer](coreboot-edk2/settings-consumers.md)
- [CPU EIST、VMX、microcode 与锁定位](coreboot-edk2/cpu-policy.md)
- [内存上限、训练缓存与 S3](coreboot-edk2/memory-training.md)
- [GGC UMA、ICH7 设备、电源恢复与 POST beep](coreboot-edk2/chipset-policy.md)
- [默认启动失败回退与手动工具](coreboot-edk2/boot-fallback.md)
- [UEFI iPXE 的集成边界](coreboot-edk2/network-ipxe.md)
- [Q35 shim 模拟边界与 SMM 布局](coreboot-edk2/q35-shim.md)
- [源码所有权、patch/overlay、三个独立构建路径](coreboot-edk2/source-build-boundaries.md)
- [CPU/MSR 与 MCHBAR 的实际显示数据](it8720f/clock-memory-data.md)
- [旧 SaSetup/QFan buffer 到本板策略的转换](asus-ui/config-access.md)

上游版本固定在 source-lock.json。RTM 保留 v5 coreboot stages，仅替换 v6 payload；
原 config/build_info 的历史身份与当前独立构建配方不可混用。
没有 AHCI/RAID、手工 PLL/FSB、电压或时序超频，不能以菜单数量代替实际 consumer。
