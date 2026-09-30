# X5450 时钟编码与 G41 MCHBAR 数据

## CPU gate和单位

只支持Intel vendor字符串且CPUID1 signature10676的已验证X5450 stepping。
MSRcd低3bit索引FsbTimesThree={800,400,600,500,1000,300,1200,0}；
MSR198 bits12:8为ratio，c000的half-ratio/dynamic-FSB分支未验证，拒绝发布。
ID7000输出(FsbTimesThree×ratio+1)/3MHz；7002输出ratio。
7001为donor特有的整数/百分位打包：(fsb/3)×10000+((fsb%3)×100)/3，
不是线性Hz/10kHz。不能拿它与真实频率单位直接相乘。

## 内存gate

PCI MCHBAR48必须fed14001且4c高位0，才接受basefed14000。
ID7003取base+c00的bits6:4，code0..5映射400/533/667/800/1067/1333MT/s。
ID7005读base+1a8 bit2决定DDR3/DDR2。
容量读base+206、+606两channel boundary，相加×64MiB；0或>8192MiB不可用。
base+111 bit1的stacked模式会影响boundary意义，未验证因此不发布容量。

## 数据意义

这些是MSR编码推导和memory-controller当前状态，不是外部频率计或PLL独立实测。
给其他CPU/不同MCHBAR/stacked配置适配时要先重新采Linux基线，不能去掉guard换成“通用G41”。
CPU_FSB真实调频仍缺ICS9LPRS916JGLF准确寄存器协议，SetFSB社区列出型号不等于本板驱动已经实现。

## 回归

provider fixture覆盖signature/MSR拒绝、BAR拒绝、data rate/type/capacity和边界。
CPU和内存显示hook使用私有7000..7005，不冒充ASUS训练数据或XMP。

源码 / 回归入口：[G41Sensors.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusAmiCompatDxe/G41Sensors.c) / [read_g41_memory.py](../../../src/boards/foxconn-g41mxe/linux/read_g41_memory.py)。
