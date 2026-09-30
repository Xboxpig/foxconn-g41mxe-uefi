# G41MXE / IT8720F 驱动：技术导航

这里的板级“驱动”由 coreboot 初始化、EDK 只读 provider 和 UI 适配组成，
不是新写了一个 Linux 内核 driver。Linux it87 v6.12 仅作为上游参考/比较基线。

- [G41/ICH7 gate、SIO config、LDN4 与 EC probe](it8720f/probe-and-io.md)
- [TMPIN mode、三秒非阻塞 ready、16-bit fan tach](it8720f/temperature-fan.md)
- [QFan 保存、四种预设与 IT8720F 自动控制](it8720f/fan-control.md)
- [五路 ADC 的 enabled/invalid 语义与 P10 分压](it8720f/voltage-adc.md)
- [X5450 MSR、BCLK 格式、MCHBAR 数据与限制](it8720f/clock-memory-data.md)
- [HWM 协议与各 UI 消费者](asus-ui/display-refresh.md)
- [设置保存和实际硬件 consumer](coreboot-edk2/settings-consumers.md)

CPU_FAN=4-pin/FAN2，SYS_FAN=FAN1；不增加不存在的风扇。
provider 不写 PWM/PLL/电压。全部预设效果、物理仪表校准和其他板型适配不属于已确认范围。
