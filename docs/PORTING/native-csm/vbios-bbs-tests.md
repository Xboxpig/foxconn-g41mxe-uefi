# P10 VBIOS、BBS / INT19 与 MBR 测试

## VBIOS身份

64KiB官方P10 Intel VBIOS SHA256
ef0fbdad30722aad774659560b08f323170091e24717c96cadac67213891199d。
原MOD比较一致。AMI将共享ROM绑定本板2e32，内部PCIR为2e02；
driver只在RAM副本改匹配ID/checksum，SPI原始ROM及执行代码/VBT保持不变。
GOP/libgfxinit不能替代legacy INT10 VBIOS。Q35用stdvga ROM，不进入真机RTM。

## BBS链

LegacyBootManager枚举BBS磁盘形成Boot####，与UEFI BootOrder连接。
成功模拟路径：PCI BIOS2.10 → LegacyBios → Boot0004 Primary Master →
EfiBootManagerBoot → LegacyBoot → INT19 → 0000:7c00。
SeaBIOS patch按完整ATA controller/channel/unit匹配boot priority，避免多controller误选。
BBS枚举只在启用且允许Legacy时进行，不拖慢默认关闭CSM的UEFI路径。

## 可执行测试

tests/mbr-test.asm保留真实MBR代码：
INT10设置/查询mode3；
INT13 AH42读LBA1并比marker；
INT1A观察PIT/PIC tick。
对应NATIVE_CSM_INT10_PASS、NATIVE_CSM_INT13_LBA_PASS、NATIVE_CSM_PIC_TIMER_PASS三项均出现。
单纯画出logo不足以覆盖磁盘/中断。Test image可用nasm生成，需要适当磁盘布局，不能误写真实磁盘。

## 未验收

真实GMA VBIOS/INT10、ICH7 SATA/PATA Legacy disk、NV across reset、独显、
Legacy USB/PXE和具体旧OS仍需专项测试。用户RTM认可说明UI流畅，不扩大这些项的证据。
ROM verifier检查Csm16/P10 RAW内容、PIC/Video/LegacyBios模块以及诊断app确实不存在。

源码 / 回归入口：[LegacyPlatform.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/G41CsmSupportDxe/LegacyPlatform.c) / [mbr-test.asm](../../../tests/mbr-test.asm) / [seabios.patch](../../../src/edk2/csm/seabios.patch)。
