# TMPIN2 模式 A/B/A 与复原责任

## 假设和风险

旧coreboot共用配置thermistor，EC51=11；P10初始化为03。固定96可能是电气模式错误，
也可能通道/布线错误，不能凭温度不合理就直接改offset或用CPU DTS冒充。
变更前确认FAN1/FAN2自动源均为TMPIN1，明确只改TMPIN2模式，不改PWM。

## 实际已授权实验

用户“允许，继续”后：只允许EC51 11/03，检查EC55=50、16-bit tach、chip IDs及自动源。
before11/96°C → diode03首秒仍96、第二秒起30–32°C（10秒）→restore11并回读→
三次after又96。FAN2全程1134–1138RPM，TMPIN1 36–37；EC13..17保持不变。
结合P10引用，这是模式错误的因果证据，不是仅看一次温度下降。

## 恢复与固件修正

实验finally及SIGINT/TERM/HUP恢复旧模式；断电/SIGKILL不保证恢复。正常结束已回读11。
随后variant设TMPIN2.mode=THERMAL_DIODE/offset0，common函数先清相反bit避免11 OR02变13。
provider在模式稳定至少3秒后才发布值，解决首个旧conversion值，不阻塞UI。
源mode函数通过1536状态转换回归，provider覆盖rollover/未ready/模式冲突。

## 不允许扩展的结论

30–32是EC二极管读数，未外部校准；不意味着CPU package温度，也不证明温度传感器精确位置。
模式切换的转速保持不变不等于所有PWM预设已经实测。
过程写工具已清理，不提供一个默认可运行的EC控制入口；以后相同实验仍须先确认接线和写入授权。

源码 / 回归入口：[overridetree.cb](../../../src/boards/foxconn-g41mxe/coreboot-overlay/src/mainboard/foxconn/g41s-k/variants/g41mxe/overridetree.cb) / [test_it8720_modes.py](../../../tests/unit/test_it8720_modes.py)。
