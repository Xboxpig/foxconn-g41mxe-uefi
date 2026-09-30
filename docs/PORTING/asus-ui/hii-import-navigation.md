# HII 导入、IFR 裁剪与原厂导航

## 二进制读取

AsusSetupHiiDxe 从 RAW FV 文件 6F7C8B8F-0F64-4BAA-95EE-06F749D73E9B 读取 Setup PE，
检查 PE image/section bounds，再找到 package list。
package list GUID 必须为 899407D7-99FE-43D8-9A21-79EC328CAC21，声明大小必须等于实际长度。
各 package 的 32-bit header：低 24 位为长度，高 8 位为 type；需要 Forms、Strings 和合法 END。
不对不完整 package 猜长度，不执行 PE entry point。

## IFR 结构

g41_hii.py 提供 packages/nodes/walk/replace_packages/rewrite_strings。scope、opcode length、end 配对
必须在输出前重解析。原 factory form IDs 保留：
2710 根、2713 Main、2714 Memory、2715 Platform、2716 Monitor、2718 Boot、271a Tools，
2858 Fan、2740 CPU、275a G41、2793 ICH7（十六进制）。
AMITSE 编译导航依赖原 question IDs，不能随意重排成新的 ID 或仅加外部 CFR 引用。

## 本板控件

私有 VarStore ID 7e01，name G41PlatformData，size 16 bytes，
GUID FB3DCA8B-EAB5-4C93-9900-5247A7211886。每个 UI setting 占一个 UINT8 slot；
这不是直接保存成 NVRAM 的 16-byte 变量，而是 ConfigAccess 的交换 buffer。
控件保留原 QID，callback flag 清除，reset-required 保留，choices/default 来自 JSON schema。
CSM QIDs 29d4/1079 使用 slot11/12。其他 11 个字段顺序必须与生成的 G41NativeOptions.h 同步。

## 测试与失败语义

test_g41_platform_ui_v5.py 检查 11 forms、navigation IDs、允许的 memory/fan 值和 PE 范围；
test_g41_csm_ui.py 检查两项 CSM 的绑定和默认值。修改 donor hash 必须拒绝。
原厂的 Z490 suppress expression、callback 和 unsupported form 不继续执行。
额外 DIMM/风扇和 AI OC 页面对象用已审计的隐藏路径，不释放仍可能被 FindWidget 引用的对象。

源码 / 回归入口：[AsusSetupHiiDxe.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusSetupHiiDxe/AsusSetupHiiDxe.c) / [g41_hii.py](../../../src/asus-ui/tools/g41_hii.py) / [test_g41_platform_ui_v5.py](../../../tests/unit/test_g41_platform_ui_v5.py)。
