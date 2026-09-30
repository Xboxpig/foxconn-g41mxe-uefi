# 默认启动、ASUS fallback 与手动工具分类

## 启动项不是名称匹配

G41MXE_FAST_SETUP 下 Shell/iPXE 使用 LOAD_OPTION_ACTIVE | LOAD_OPTION_CATEGORY_APP。
已保存的旧固件工具按完整 device path 等长且 CompareMem 相同迁移 category，
不是看到描述为 Shell 就改一个可能属于用户的启动项。
这使工具仍可手动选择/BootNext，却不作为缺省 OS 自动尝试。

## 无可用启动项的流程

BDS 按已保存的 OS Boot#### device path 连接所需 controller 并尝试启动。
PlatformBootManagerUnableToBoot 获取 Boot Manager Menu，进入 UiApp→ASUS SendForm。
退出 Setup 后重新读取 BootOrder/Boot####，只自动尝试 ACTIVE 且 CATEGORY_BOOT 项；
全部失败会再次进入 Setup，不自动执行 Shell/iPXE，不在此插入 ConnectAll。
Menu 获取失败记录 EFI_STATUS 并返回；不能声称 UI 缺失时也必然能显示首页。

## 设备发现与保存限制

这不是完整禁用硬件扫描：当前启动项按需连接，Device Manager 请求时才全局发现。
用户插入新盘但未注册 OS entry，可能先进入 Setup，不能误判磁盘不存在。
BootOrder 只能重排原 entries；相关保存验证见 [ConfigAccess](../asus-ui/config-access.md)。
CSM 架构过滤叠加在 EfiBootManagerBoot，Legacy-only 的工具豁免另见
[CSM policy](../native-csm/platform-policy.md)。

## 源码与证据

源码在 board/patches/edk2.patch 的 PlatformBootManager.c / BmBoot.c / UiApp。
测试与历史 Q35 观察验证代码路径，真机 v6 获流畅 RTM 反馈。
“缺省项无效”“BootNext工具”“修改顺序后退出”“新硬盘发现”不是同一场景；
本次整理没有额外真机测试这些组合，也不承诺 fallback 固定用时。

源码 / 回归入口：[edk2.patch](../../../src/boards/foxconn-g41mxe/patches/edk2.patch)。
