# 技术记录索引

六个主题入口，29 篇独立技术细节。按实现机制拆分，不按每日尝试复制长日志。
这些是已核对源码和历史观察的工程记录；正式认可范围仅见
[RTM 基线](../RELEASE/p-rtm1-baseline.md)，未验证事项不会因为文档拆分而晋级。

## ASUS 原厂 UI 移植（5 篇）

主题入口：[ASUS UI](asus-ui.md)。

- [Donor、FV 文件、协议 GUID 与兼容 ABI](asus-ui/donor-and-fv.md)
- [HII package、IFR scope、VarStore 与原厂导航 ID](asus-ui/hii-import-navigation.md)
- [ConfigAccess、NV 属性、BootOrder 与非事务保存边界](asus-ui/config-access.md)
- [输入 hash、hardware-safe patch、RVA 与 PE section](asus-ui/binary-patching.md)
- [HWM sentinel、HII 定时更新与多路显示格式](asus-ui/display-refresh.md)

## coreboot + EDK II / G41 平台（9 篇）

主题入口：[coreboot + EDK II](coreboot-edk2.md)。

- [16 MiB flash map、payload 解压、MRC 与 SMMSTORE](coreboot-edk2/flash-map-variables.md)
- [Native slot、变量名、默认值和 consumer 总表](coreboot-edk2/settings-consumers.md)
- [CPU：EIST、VMX、MSR lock 和 microcode](coreboot-edk2/cpu-policy.md)
- [内存：rate cap、SPD、MRC 版本、warm reset 和 S3](coreboot-edk2/memory-training.md)
- [芯片组：UMA、ICH7 设备/电源/NMI 和 POST beep](coreboot-edk2/chipset-policy.md)
- [启动：默认 OS、手动工具分类与 ASUS fallback](coreboot-edk2/boot-fallback.md)
- [网络：UEFI iPXE 与 Legacy PXE 的边界](coreboot-edk2/network-ipxe.md)
- [Q35：CAR/DRAM、flash XIP、SMM save-state 和模型边界](coreboot-edk2/q35-shim.md)
- [工程：源码所有权、patch/overlay 和三个构建路径](coreboot-edk2/source-build-boundaries.md)

## Setup 性能诊断（3 篇）

主题入口：[Setup 性能](setup-performance.md)。

- [三处 ConnectAll 与 DeviceManager constructor 延后](setup-performance/bds-lazy-connect.md)
- [Pool ASSERT 链表检查与 PcdDebugPropertyMask 03→02](setup-performance/dxecore-assert.md)
- [GDB / CBMEM 计时、串口消费、截图与缓存假设](setup-performance/trace-and-evidence.md)

## Linux 采集和因果验证（3 篇）

主题入口：[Linux 传感器验证](linux-sensors.md)。

- [只读基线、硬件身份与 index/data 串行保护](linux-sensors/read-only-baseline.md)
- [P10 token→callback→寄存器/ADC 公式/初始化表](linux-sensors/p10-reverse-reference.md)
- [TMPIN2 授权 A/B/A、conversion 过渡值与恢复](linux-sensors/tmpin2-aba.md)

## IT8720F 驱动 / 实际数据（5 篇）

主题入口：[G41MXE / IT8720F](g41mxe-it8720f.md)。

- [PCI/SIO gate、LDN4、EC I/O 与 counter 条件](it8720f/probe-and-io.md)
- [温度 mode、三秒非阻塞 ready 与 16-bit tach](it8720f/temperature-fan.md)
- [ADC enabled、五路分压、整数有效性与仪表限制](it8720f/voltage-adc.md)
- [X5450 MSR、donor BCLK 编码、MCHBAR 容量/类型/速率](it8720f/clock-memory-data.md)
- [QFan buffer、四种预设、coreboot 写入与接线边界](it8720f/fan-control.md)

## 原生 UEFI CSM（4 篇）

主题入口：[Native CSM](native-csm.md)。

- [Platform services、本次 boot volatile policy 和启动过滤](native-csm/platform-policy.md)
- [IVT/BDA、PAM、FarCall shadow 写权限和恢复](native-csm/low-memory-pam-thunk.md)
- [PIC、PIRQ/ELCR、RCBA、bridge swizzling 与 Q35 差异](native-csm/pic-pirq-routing.md)
- [P10 VBIOS、BBS→INT19 与 MBR INT10/INT13/PIT 测试](native-csm/vbios-bbs-tests.md)

## 如何沿记录找到实现

通用上游源码在 src/coreboot/upstream、src/edk2/upstream；已有文件的本板修改在
src/boards/foxconn-g41mxe/patches，新文件在该目录 coreboot-overlay/edk2-overlay。
ASUS 二进制和通用 HII 工具在 src/asus-ui；本板生成器/allowlist/schema 在 board/asus-ui。
不要在 build 里找可维护真源，也不要把 closed donor 二进制称为 ASUS 源码。

可执行入口：[test.sh](../../tools/test.sh)、[RTM verifier](../../tools/verify-rtm.py)。
实际结果见 [验证摘要](../../releases/g41mxe-rtm1/evidence/validation.md)。
Host mock、Q35 真实执行、Linux 历史采样和用户真机反馈四类证据必须保持区分。
