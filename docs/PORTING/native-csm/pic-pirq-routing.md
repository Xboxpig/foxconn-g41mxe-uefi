# PIC、PIRQ/ELCR 与 PCI bridge swizzling

## 表结构与G41来源

G41Routing构造32个root-device的$PIR表，router位于bus0 dev31，
PIRQ register表60/61/62/63/68/69/6a/6b。
IRQ候选bitmap0e20为5/9/10/11，priority11→10→9→5。
G41普通设备route3210；dev27..31读LPC RCBA+3140+(31-device)×2，
每pin占4bit，取&7为link，匹配coreboot ACPI _PRT生成的实际路由。

## 桥后设备

LocateHandleBuffer/PCI_IO构建secondary bus→parent bus/device表。
Framework传进的Device是devfn编码，先检查低3bit=0再>>3。
向root逐层Pin=(Pin+Device)&3；未知parent返回NOT_FOUND，256层未回root返回DEVICE_ERROR。
不是对任意bus直接用device%4猜中断。

## PIRQ到IRQ

已有active route保留；只有disable bit80或IRQ0才改选IRQ11。
最终用DEF8验证可用IRQ，ELCR端口4d0+irq/8对应bit置level。
推荐bitmap与允许保留现有路由的mask是两个不同范围，不把它们写成同一常数。
8259 driver、LegacyInterrupt、ELCR和PCI配置共同工作，不只安装一个协议GUID。

## Q35差异

Q35普通slot用E..H：(device+pin)&3再+4；dev30固定E..H；
集成dev25/26及其余读实际RCBA偏移。这是QEMU ICH9模型，不能套进G41 ICH7。
handle allocation失败有检查并释放buffer。INT1A/PIT测试是PIC timer真实路径证据，
不构成所有PCI外设IRQ的真实主板验收。

源码 / 回归入口：[G41Routing.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/G41CsmSupportDxe/G41Routing.c) / [LegacyInterrupt.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/G41CsmSupportDxe/LegacyInterrupt.c)。
