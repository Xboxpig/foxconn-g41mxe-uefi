# GDB/CBMEM 计时、截图与证据边界

## 推荐观察顺序

同一次启动先记录最后stage、再采CBMEM；Linux可用时sudo cbmem -c。
阶段覆盖BDS hook、LoadImage/StartImage、constructors、UiApp最早入口、console、HII、SendForm。
短期ACPI PM counter校准64-bit TSC，避免24-bit PM timer约4.7秒回绕对90秒测量造成假值；
频率变化时这种trace不是精密计时器。

## 排除错误证据

GPIO/SPI灯闪烁不等于全片顺序读取，GetVariable也不等于SPI重读。
framebuffer MTRR类型不包含PAT/页表组合，Q35观察到WC→UC不够判定真机effective memory type。
没有真机吞吐/PAT证据，因此本次没有缓存属性patch。
G41Sensors三秒ready检查是非阻塞时间戳，未ready直接N/A，不是每次读都等待三秒。

## QEMU 输出与截图

未读的serial pipe可以让客体阻塞，诊断用持续消费的输出或普通文件。
HMP必须完整消费初始greeting和每个command结束prompt；旧截图可能误报“无刷新/死锁”。
OsIndication模拟Setup请求不是键盘ESC；sendkey可靠性与UI响应需分开验证。
GDB symbols必须与FD匹配，别使用邻近但错误的baseAddress。
Q35没有G41/IT8720F时N/A是预期，不证明真机传感器失效。

## 结果保存

过程trace脚本/log已按用户要求移出，保留方法、最终ROM身份和明确已观察到的结果。
当前诊断标记源G41SetupTrace.h仍保留，但RTM G41MXE_SETUP_TRACE=FALSE。
以后需要新trace先构建新身份的诊断ROM，不覆盖已认可RTM。

源码 / 回归入口：[G41SetupTrace.h](../../../src/boards/foxconn-g41mxe/edk2-overlay/MdeModulePkg/Include/Library/G41SetupTrace.h)。
