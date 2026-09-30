# P10 标签、callback、ADC 公式与初始化引用链

## 固定输入

官方P10与MOD的已比较amibody_1b字节一致；不外推整ROM相同。
body SHA256 14bfa0dc1d7d33e45c8047d95523cd0d03b0214cf2121a37043137013dd2829f；
amiboot SHA256 56bb4ec01b6db5ab8b9009c64a53bf184d04a83456c955881b23ca2936eb3232。
必要body/语言包/boot binary在board/assets/p10。

## 电压引用链

语言token30..34 → body offset30a97六字节记录[0145,token,callback] →
callbacks426a/4279/4288/4297/42a6 → callback前四字节ADC表 → 公共换算函数。
这段运行地址与文件offset差2f1b1，不能把两者直接相等。
表[register,denominator,numerator,mode]：
33417=20 01 01 00；33426=21 01 01 00；33435=24 01 01 00；
33444=23 64 a8 00；33453=22 01 04 00。
mode0公共代码334ee..33514为raw×16×numerator/(1000×denominator)，输出V整数和三位小数；
固件provider换成整数mV，按相同比例截断。EC reader文件offsetbbdb，通过far call4000:b81c使用。

## 温度与初始化

CPU温度token2e→callback4147→EC29；
System温度token2f→callback4153→EC2a，因而TMPIN2标签有来源而不是猜测。
boot dispatch bc→6fc2，载入6f14的23组三字节记录，[index,and_mask,or_mask]。
表6f17=51 00 03，初始化公式(old & mask)|value，无条件使EC51=03。
这张表没有写EC55，不能据此证明后续所有路径都不改它。

## 证据层次

静态引用证明公式/标签/初始化意图；Linux A/B/A证明本板mode错误导致96。
没有外部仪器就不能称为物理校准。原验证脚本属于一次性过程，源码表和输入binary已保留，
重做分析应先核对hash和运行/文件地址差，再用真实采样交叉验证。

源码 / 回归入口：[amibody_1b.rom](../../../src/boards/foxconn-g41mxe/assets/p10/amibody_1b.rom) / [amiboot.rom](../../../src/boards/foxconn-g41mxe/assets/p10/amiboot.rom)。
