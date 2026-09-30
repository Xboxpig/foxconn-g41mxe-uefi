# Linux 传感器验证：技术导航

真实采样先核对 PCI/SIO/EC 身份；coretemp、TMPIN 和 ADC 各有不同物理来源。
不为采一组数值自动加载会初始化 PWM 的驱动，不把历史数据写成今天重新采集。

- [只读采集前置条件、端口索引与原始基线](linux-sensors/read-only-baseline.md)
- [P10 token→callback→寄存器/公式/初始化的反向引用](linux-sensors/p10-reverse-reference.md)
- [TMPIN2 的授权 A/B/A、恢复责任与 mode 因果证据](linux-sensors/tmpin2-aba.md)
- [固件 provider 的探测与 I/O 条件](it8720f/probe-and-io.md)
- [温度和风扇计算](it8720f/temperature-fan.md)
- [电压公式及校准限制](it8720f/voltage-adc.md)

Linux 参考与只读工具保存在 board/linux；一次性 EC 写入实验工具不作为交付工具。
用户此前确认传感器按预期工作，不能扩大为所有 PWM/电压/超频控制都已验证。
