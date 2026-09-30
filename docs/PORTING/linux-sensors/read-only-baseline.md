# Linux 只读基线采集与端口保护

## 前置条件

通过SSH连接目标Linux后，先核对PCI host2e30/LPC27b8，不凭SSH别名判断硬件。
确认IT8720F 8720/rev08、LDN4 enabled、base0a10、EC身份与monitor已启用。
read_g41_sensors.py拒绝it87已加载，避免内核hwmon和用户态同用index/data端口。
读取EC仍需要写“索引选择”端口，这不是写寄存器数据；工具恢复旧索引，不改变PWM/模式。

## 采集字段

记录EC00、0a、0c、13..19、20..2a、50/51/55/58，输出原始值，不先强行加电源轨标签。
同步记录coretemp每个Core、CPU型号和memory信息，明确不是同时刻同一物理传感器。
初始CPU FAN2约1134–1142RPM，TMPIN1约37–38、TMPIN2=96、TMPIN3=80无效。
ADC50=ff，原始采样可由P10公式再解释，不能按电压“看着像”匹配引脚。

## 许可与复现

Linux driver参考保存在linux/it87-linux-v6.12.c；只读工具在同目录。
读取/dev/port、/dev/mem、MSR需要适当权限，不能为绕过权限自动启用危险内核选项。
MSR模块曾临时加载只读后卸载，不据此认为所有CPU都有相同MSR。
本次整理不SSH、不加载驱动、不写硬件，也不重新声称这些历史值是今天新采集的。

## 输出边界

原始ADC、fan count和mode优先保存；换算见[电压](../it8720f/voltage-adc.md)及
[温度/风扇](../it8720f/temperature-fan.md)。原采集JSONL属于过程log，已移出工作目录；
数值、来源和验收界限转入这些记录。真正PWM测试必须另有明确授权和风扇安全判据。

源码 / 回归入口：[read_g41_sensors.py](../../../src/boards/foxconn-g41mxe/linux/read_g41_sensors.py) / [read_g41_memory.py](../../../src/boards/foxconn-g41mxe/linux/read_g41_memory.py)。
