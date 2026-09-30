# X5450：EIST、VMX 和 microcode 的实际应用

## 存储到 CPU 初始化

ASUS 控件 → G41PlatformData slot0/1 → ConfigAccess 校验 → coreboot NV GUID 下的
UINT32 eist/vmx → 下一次 coreboot CPU/MP 初始化。不是 AMITSE 直接写 MSR，
也不提供 X5450 倍频、电压或 PLL 调频。两项默认均为 1。

源码真源为 [coreboot 板级 patch](../../../src/boards/foxconn-g41mxe/patches/coreboot.patch)，
目标文件是 model_1067x_init.c 和 mp_init.c；菜单身份见 [schema 总表](settings-consumers.md)。

## EIST 开关及锁

eist_supported 要求 CPUID.1:ECX bit7，且 IA32_PLATFORM_ID bit17 未置位。
实际 eist = supported && get_uint_option("eist", 1)。
configure_misc 先清 IA32_MISC_ENABLE bit16，再按设置启用；支持 EIST 的 CPU 再锁 bit20。
把“支持”和“本次启用”分开，才能在关闭 EIST 时仍执行正确的锁定流程。
TM2 在这个既有初始化路径中依赖 eist 及 CPUID bit8，不应声称关闭 EIST 仅改变界面标志。
ACPI/OS 的 P-state 使用还受 OS 电源策略影响，不能把瞬时频率等同固件开关。

## VMX 与 SMM

pre_mp_init 读取一次 vmx，并继续载入 microcode。
各 CPU 的 per_cpu_smm_trigger 用 set_feature_ctrl_vmx_arg(vmx_enabled)；
有 SMRR 与无 SMRR 路径保留其各自的 feature-control/lock 处理。
锁定 MSR 不是 DXE 页面内可即时反复切换的状态，修改保存后必须重启。
Q35 的 save-state 兼容分支另见 [shim](q35-shim.md)，不是 X5450 的原生布局。

## 保留输入与验收

microcode 六个输入保存在 board/assets/microcode，覆盖 10676/10677/1067a 的既有 platform flags。
以实际 CPUID/platform 匹配选择，不因为 X5450 商品名就任选一份。
整个 coreboot 独立构建通过，ConfigAccess 值域测试通过；本次没有真机逐项切换、
跨 reset 比较 MSR 或运行虚拟机的专项验收。UI 流畅不证明 VMX/EIST 的每一种状态。

源码 / 回归入口：[test_g41_native_config.c](../../../tests/unit/test_g41_native_config.c)。
