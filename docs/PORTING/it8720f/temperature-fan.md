# 温度 mode、等待期与 16-bit tach

## 温度

CPU token1fb3取EC29；EC51&09必须非零，接受0..126°C，>=127不可用。
System token1fb9要求(EC51 & d2)==02，且EC55 bit7未置位，保证TMPIN2 diode与无冲突路由。
模式错误时清ready并更新tempStart；模式正确时按counter mask处理wrap，
GetTimeInNanoSecond(elapsed)>=3,000,000,000才发布EC2a。
等待期间直接返回sentinel，不使用Stall，不把旧96发布出来。
TMPIN3=80无效，未提供Package/VRM/Chipset假读数。

## 风扇

ReadFan index0=SYS/FAN1，index1=CPU/FAN2。
EC0c对应bit必须启用16-bit模式；8-bit/divisor路径未适配。
最多3次读high(18+index)→low(0d+index)→high，只有high相同才组合count。
count0不可用；countffff表示没有tach pulses，返回真实故障意义0RPM，但无法区分停转与拔掉。
其他count：1350000/(count×2)，整数截断；count592→1140RPM。

## coreboot mode修正

ITE common enable_tmpin在IT8720F分支清相反analog bit再写目标位。
TMPIN2从11切diode应变03，不是13。disabled通道不修改旧值。
板级variant只覆盖本G41MXE，其他g41s-k板不继承这个未经其测试的diode选择。
Test为3 channels ×256 old states ×2 modes，另有11→03/disabled检查。

## 展示限制

0°C和0RPM可能有意义；N/A是采集不存在/格式不支持，不与零统一。
CPU diode与CPU Core DTS不同；无tach脉冲是可观察故障，不报告虚构“风扇已拔掉”。
UI刷新周期、风扇控制循环和三秒mode就绪条件分别存在，不应混为一项等待。

源码 / 回归入口：[G41Sensors.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusAmiCompatDxe/G41Sensors.c) / [coreboot.patch](../../../src/boards/foxconn-g41mxe/patches/coreboot.patch) / [test_it8720_modes.py](../../../tests/unit/test_it8720_modes.py)。
