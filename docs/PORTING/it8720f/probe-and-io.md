# IT8720F Probe、EC index/data 与退出保护

## 硬件 gate

G41Sensors.ProbeEc先清mEcBase/mTempReady/mCounterMask。
PCI0:0.0必须2e308086，LPC0:31.0必须27b88086，否则不探SIO（Q35只显示N/A）。
进入ITE config在2e依次写87/01/55/55；20/21读ID8720，保存旧LDN7，
临时选LDN4，读30 active、60/61 base，恢复旧LDN，然后index2/data2退出。
只有active bit0且base0a10才接受；再检查EC58=90、EC00 bit0启用。

## 读数入口

EC index=base+5=0a15，data=base+6=0a16。ReadEc只选择index并读data。
固件provider在读取集合时RaiseTPL(HIGH_LEVEL)，返回前RestoreTPL；Linux工具另行恢复旧index。
不要声称firmware每次ReadEc都保存/恢复index，源码没有这个动作。
TPL保护属于DXE上下文，不等于能任意与SMM或内核hwmon并发访问，不能跨环境照搬其串行性假设。

## Counter条件

GetPerformanceCounterProperties需start0、end非零且mask&(mask+1)=0，支持up-counting的2^n周期。
不匹配的timer不会用错误wrap算法发布System温度；ready保持不可用。
初次Probe完成记录tempStart，不在Probe中阻塞等待。
访问未被支持的平台不能用默认0a10地址碰运气，也不自动启用被关闭的EC。

## 回归入口

test_g41_sensors.c编译真实provider，mock PCI/config/EC，验证chip mismatch不触碰SIO、
LDN/base/monitor拒绝、TPL配对、timer rollover与真实板fixture。
“mock通过”只证明这些分支/计算，不等于对任意IT87型号通用。

源码 / 回归入口：[G41Sensors.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusAmiCompatDxe/G41Sensors.c) / [test_g41_sensors.c](../../../tests/unit/test_g41_sensors.c)。
