# 二进制 patch 身份、RVA 与 PE 边界

## 输入链

最终 HII/页面生成只接受已审计中间输入：
Setup-core2-zero-rpm.efi SHA256 b2811e1a3db1bb2372574c54cf9400d3315ae2fed9d6dee7a4b6b8b8e8cc6bc7；
AMITSE-hardware-safe.efi SHA256 dc2fa602c5eacccb3c2923d0dd13625213ad173c6d36239b3daf1344f3a171c4。
保留原 CAP 和必要 checkpoint；不能声称只凭最终 generator 就从任意 CAP 自动移植。

## Hardware-safe patch

patch_amitse_hardware_safe.py 的精确输入 SHA256 为
7df33b6d2572d9e925d79193ccb109cb823051a4b6e7afc4d7d5b7d92f65b4a8。
PM timer sites b51/b6b/eb7c/eb98 将 mov edx,1808 改为 mov edx,0508。
3d9d8、ba414、465d4 的已审计入口在预期 prologue 前返回；
ca428 跳到 ca477，跳过 donor SIO 2e/2f 数据写入，保留后续输出初始化。
这些 offset 只对绑定输入有效，不是器件型号通用表。

## Display/PE patch

display-validity hook base 1dd080。RIP-relative/jmp displacement 以实际 RVA 计算，
注入前检查被替换指令，保留 x64 register、stack alignment、EFI shadow space。
扩展末 section 后一致更新 raw/virtual size、SizeOfImage、initialized-data size，清除旧 PE checksum。
最终 allowlist patch 把 562e2 的 donor 风扇枚举上限改为 2，并在 adeb4 接入 ancestry 隐藏路径。
父容器被隐藏时其 children 也不能留下可点击热区。

## 回归规则

生成 v6 Setup/AMITSE 必须逐字节等同归档 assets，且 donor 任意篡改都会拒绝。
tests 检查 PE bounds、section 前部不变、编译导航 ID、默认值与 scope。不要忽略 hash guard，
也不要只看生成文件大小就认为 patch 成功。原 donor 的地址与 injected code 的地址不能混用。

源码 / 回归入口：[patch_amitse_hardware_safe.py](../../../src/boards/foxconn-g41mxe/asus-ui/patch_amitse_hardware_safe.py) / [patch_amitse_display_validity.py](../../../src/boards/foxconn-g41mxe/asus-ui/patch_amitse_display_validity.py) / [patch_g41_platform_ui.py](../../../src/boards/foxconn-g41mxe/asus-ui/patch_g41_platform_ui.py)。
