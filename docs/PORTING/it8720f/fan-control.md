# QFan 到 IT8720F：控制预设与接线边界

## 保存到初始化

AsusQFanSetupData 为固定 144 bytes，GUID EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9。
CPU control/profile 在 offsets0/8，SYS 在18/20（十六进制）。
ConfigAccess 校验并保存；下一启动的 coreboot option bridge 分别读
cpu_fan_profile 和 chassis_fan_profile，由 IT8720F init 应用，不在 HII timer 内写 PWM。
CPU_FAN 已由用户确认 4-pin，对应 FAN2；SYS_FAN 对应 FAN1。

## 允许的转换

control0 → Full Speed，绝不是 Fan Stop。
control1/3 接受已审计布局；control2 的 DC 模式拒绝。
profile0 Standard→Balanced1；profile1 Silent→0；profile2 Turbo→Performance2。
Manual 曲线和额外 fan header 没有兼容算法，不开放。
[转换函数](../../../src/boards/foxconn-g41mxe/coreboot-overlay/src/drivers/efi/asus_g41_policy.h)
先检查长度、CPU selector、控制和 profile，失败保持 native fallback。

## EC 自动控制参数

| preset | mode | tmp_off/start/full（°C） | pwm_start | slope |
| --- | --- | --- | --- | --- |
| Silent0 | Smart Automatic | 30 / 35 / 75 | 15 | 6 |
| Balanced1 | Smart Automatic | 25 / 30 / 65，板级默认 | 20 | 10 |
| Performance2 | Smart Automatic | 20 / 25 / 55 | 35 | 12 |
| Full Speed3 | FAN_MODE_ON | 不使用自动阈值 | 不使用 | 不使用 |

两路自动源保持 TMPIN1，tmp_delta3、smoothing1 来自板级/预设；不是 UI 显示的 System TMPIN2。
ite_ec_init 通过 common env_ctrl 的寄存器编码写阈值、起始 PWM、slope 与 mode。
表中 pwm_start 是配置单位，不能按 raw register 数值直接理解。
配置结构先从 conf->ec 复制再调整，不把一个 fan 的状态共享成所有端口值。

## 不把显示反馈扩大为控制验收

传感器显示正常及 TMPIN2 A/B/A 中风扇稳定，不等于四个 PWM preset 都实测通过。
预设保留已有 tmp_off 行为，不能承诺风扇永不停转；低温、风扇启动 duty、线材与电气能力要实测。
没有基于 CPU Core DTS 的软件闭环，没有 manual curve/DC、风扇自动校准或真实 Fan Stop 开关。
provider 保持只读，控制动作由 coreboot 初始化承担。

源码 / 回归入口：[coreboot.patch](../../../src/boards/foxconn-g41mxe/patches/coreboot.patch) / [env_ctrl.c](../../../src/coreboot/upstream/src/superio/ite/common/env_ctrl.c) / [test_g41_policy.c](../../../tests/unit/test_g41_policy.c)。
