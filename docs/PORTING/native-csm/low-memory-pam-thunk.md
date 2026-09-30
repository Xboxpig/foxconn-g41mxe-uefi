# IVT/BDA、PAM shadow 与 16-bit thunk 权限

## 低地址所有权

现代DXE拒AllocatePages(0)。UefiPayloadEntry在native CSM构建时为page0建立allocation HOB，
LegacyBios用ACCESS_PAGE0_CODE访问IVT/BDA，不关闭全局NULL-page保护。
低地址分配失败必须返回，不能继续使用未分配的thunk/BIOS区。
PAM边界为c0000..fffff：12个16KiB段和f0000的64KiB段。

## G41/Q35 PAM

c0000/c4000由91低/高nibble；之后92..96同样每个两个16KiB段，
f0000..fffff由90高nibble。read位分别01/10，write位02/20。
00不走DRAM、01只读、10只写、11正常。LegacyRegion2验证start/length/granularity，
避免start+length溢出与越界；BootLock返回unsupported而非假锁定。

## 关键失败与修正

Csm16有shadow内mutable state/ExtraStack，只把BIOS作为只读ROM会破坏FarCall。
InternalLegacyBiosFarCall快照原write attributes→临时unlock→cache flush→调用→恢复原状态。
曾仅在Int86修正且无条件relock，会把外层option-ROM操作锁回只读，导致VBIOS triple fault。
最终按调用前状态恢复，不能把read/write权限全局永久放开。

## 证据边界

Q35 MBR/INT10/INT13/PIC测试覆盖该链真实执行。LegacyRegion.c和兼容Thunk.c源被保留。
Q35可执行不证明G41所有shadow/option-ROM路径；真实GMA仍待专项验收，不能用一次UI启动代替。

源码 / 回归入口：[LegacyRegion.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/G41CsmSupportDxe/LegacyRegion.c) / [Thunk.c](../../../src/edk2/compat/IntelFrameworkModulePkg/Csm/LegacyBiosDxe/Thunk.c)。
