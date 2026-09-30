# ADC 电压通道、比例与整数有效性

## 原厂映射

对应链见[原版引用](../linux-sensors/p10-reverse-reference.md)。

| ASUS ID | Rail | EC ADC | mV公式 |
| --- | --- | --- | --- |
|20cb|Vcore|20|raw×16|
|20d3|DRAM|21|raw×16|
|20d1|3.3V|24|raw×16|
|20cf|5V|23|raw×16×168/100，截断|
|20cd|12V|22|raw×64|

IT8720F不带Linux it87某些型号的12mV/10.9mV标记。基本16mV，外部分压比例来自P10表，
不是根据“接近标准电压”反推。provider以UINT32计算先乘后除，避免丢失比例。
EC50 bit(register-20)需enabled；raw0和ff拒绝，别将断路/端点码当rail电压。

## 真实基线与展示

历史enabled基线：Vcore1120–1200mV，DRAM1632，3.3V3360，5V5026，12V11840–11904。
HII格式value/1000 + value%1000（三位小数）；EZ的getter/formatter需独立validity hook。
0x8000请求flag的无效输出7fff，旧数值consumer仍用0。
显示电压不意味着支持调压，provider没有写ADC、PWM、电压控制。

## 验证与风险

host tests覆盖五路公式、比例截断、ADC disabled、0/255、两种ABI。
P10 formula和真实采样一致不等于外部仪器校准；DRAM1632mV未校准，不改比例“修正显示”，
更不能为了显示1.5V去改变供电。未有label/reference的其他ADC通道继续不发布。

源码 / 回归入口：[G41Sensors.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusAmiCompatDxe/G41Sensors.c) / [test_g41_sensors.c](../../../tests/unit/test_g41_sensors.c)。
