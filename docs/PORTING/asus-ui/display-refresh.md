# HWM validity、HII 更新与 AMITSE 数值 ABI

## Provider 协议

78039142-4378-48EF-BB5D-F63BF2C5DEB5 的首个 method 为 UINT32 EFIAPI Read(UINT16 Id)。
请求 bit15 表示接受 display sentinel 7fff；provider 随后 Id &= 7fff。
旧无标志消费者缺失返回 0，不能全球改成 7fff。私有显示请求 f000..f005 实际分派到7000..7005，
它们不是 donor HII string token。

## HII 更新

G41HiiSensors 定时事件为 EVT_TIMER|EVT_NOTIFY_SIGNAL、TPL_CALLBACK、period=10000000（100ns 单位，一秒）。
LocateProtocol 失败立即退出；相同数值不重复 HiiSetString。
温度输出“%u C”，风扇“%u RPM”，电压按 value/1000 与 value%1000 输出三位小数。
CPU brand 从 CPUID 80000002..80000004 提取，UTF-16 写入 token261。
HII unit 3 标记 ratio-based MHz；memory data rate 使用 MT/s，容量 MB，避免 MHz/MT/s 混用。

## 多个显示消费者

EZ/Monitor/Advanced 侧栏/曲线/数值输出并非同一个路径。
fan sentinel 显示 N/A 时，数值输出仍需为 0，不向共享 curve 返回32767。
合法 0°C、saturated tach 的0 RPM不能统一当missing。电压禁用、协议不存在与有效零值要按各 ABI 区分。
SP/Cooler/Prediction 来自 donor AI 估计，不是 EC 采样，必须隐藏而非使用 TMPIN 替代。

## 验证边界

真实 provider 与 donor formatter 隔离回放曾覆盖64次调用，8次联合调用使用实际EC fixture：
CPU37、System31、Vcore1.120、DRAM1.632，模式错误、等待期、rollover、ADC禁用。
printf/端口/内存服务仍为mock。真机显示反馈单独登记；一秒HII采样周期不等于UI必须一秒一刷。

源码 / 回归入口：[G41HiiSensors.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusSetupHiiDxe/G41HiiSensors.c) / [G41Sensors.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusAmiCompatDxe/G41Sensors.c)。
