# Q35 shim：能覆盖什么，不能覆盖什么

## 模型前提

QEMU Q35 是 Q35/ICH9，不是 G41/ICH7/IT8720F 完整模型。
CONFIG_G41MXE_Q35_SHIM 是诊断开关，RTM 必须关闭，诊断镜像禁止刷入主板。
shim 将临时 CAR 放进 QEMU 已有 RAM（DCACHE_RAM_BASE10000），不验证真实 cache-as-RAM。
x4x early init 后跳过真实 SPD/DRAM training，利用 QEMU RAM 做 CBMEM/handoff。

## 内存和 flash

RAM top 由 CMOS34/35 推导，另保留 TSEG8MiB；
northbridge resource 分支按 Q35 RAM 发布 low-memory/MMIO/reserved ranges。
QEMU parallel flash command/status 状态影响整片；romstage 仍 XIP，
q35_preram_media.c 让 boot_device_rw 返回只读映射，写/擦除延后到 ramstage/SMM。
这不是 G41 SPI controller 的吞吐/寻址仿真，不能验证真实 SPI 性能。

## SMM save-state

Q35 支持的 revision00020000为legacy、00020064为amd64 layout。
union 把 smm_revision offset 对齐，static_assert 检查；不同分支各写正确 smbase 字段。
未知 revision 打错误并拒绝继续该 relocation，不任意猜布局。
真机仍使用原 smm_relocation_handler，shim 才改 SMM size/handler/ROM media。
只有 DXE 页面可运行但 SMMSTORE 失败的镜像，不算完成平台初始化。

## 已覆盖与边界

适合执行 coreboot 后续 stage、EDK payload、AMITSE ABI、Boot Manager、thunk/INT10/INT13/PIC，
也支持 GDB 追踪 Setup 的 constructor 与 allocator 热点。
不覆盖 X4x 训练、实际传感器、电压/PWM、GMA 显示电气、ICH7 DMA/IRQ 全路径和 SPI persistence。
CSM 平台诊断有明确 Q35 host/LPC gate，routing 与 G41 分开；
[CSM测试](../native-csm/vbios-bbs-tests.md)与[trace](../setup-performance/trace-and-evidence.md)记录观察范围。
历史过程运行脚本/log 已清理，保留 shim 源码和方法，不把普通 Q35 当作本板实测。

源码 / 回归入口：[coreboot.patch](../../../src/boards/foxconn-g41mxe/patches/coreboot.patch) / [q35_preram_media.c](../../../src/boards/foxconn-g41mxe/coreboot-overlay/src/mainboard/foxconn/g41s-k/q35_preram_media.c)。
