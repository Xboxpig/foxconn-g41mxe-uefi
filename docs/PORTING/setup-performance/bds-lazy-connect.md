# BDS 到 Setup：三处 ConnectAll 的定位与延后

## 真实调用顺序

热键通知先显示Entering Setup；BDS之后继续PlatformBootManagerAfterConsole。
菜单应用StartImage又可能执行BootManagerMenu入口；UiApp的library constructors先于正式入口运行。
第三条实际GDB链为：
StartImage → _ModuleEntryPoint → ProcessLibraryConstructorList →
DeviceManagerUiLibConstructor → EfiBootManagerConnectAll。

## 为什么拔外设无效

IDE/SATA、USB、PCI和网络控制器仍在，空port/驱动状态也能触发探测等待。
第一个候选只移除平台hook扫描，真机仍90秒；第二个又移除BootManagerMenu扫描仍漏constructor。
这个历史不能改写成“一次移除就解决”。原生UiApp也走constructor，因而非ASUS专有瓶颈。

## 实际策略

G41MXE_FAST_SETUP使三处不在进入首页时ConnectAll/RefreshAllBootOption。
Device Manager真正创建form时按需连接，非fast路径保留上游constructor行为。
UiEntry(TRUE)避免又在UiApp重复扫描；默认console已由BDS连接，不再重复连接。
不全删Boot/Device Manager扫描，不以存储列表暂时为空判定硬盘坏。

## 验证

源码和目标代码调用引用检查 + Q35 GDB/串口确认进入SendForm前未探测SATA/AHCI。
真机用户反馈Shell exit后约3秒进ASUS，之后才处理绘制卡顿。
Q35 OsIndication=BOOT_TO_FW_UI不是ESC键实测，文档必须区分入口。
涉及源码在board/patches/edk2.patch的PlatformBootManager、BootManagerMenu与DeviceManagerUiLib。

源码 / 回归入口：[edk2.patch](../../../src/boards/foxconn-g41mxe/patches/edk2.patch)。
