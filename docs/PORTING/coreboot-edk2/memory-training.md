# G41 内存 rate cap、MRC cache 与重训练

## UI 与 coreboot 单位

ASUS SaSetup buffer 固定 1282 bytes；offset0x18e 为 little-endian UINT16。
允许 0/1067/1333，分别映射 coreboot max_mem_speed 的 0/1066/1333。
这是最大 data-rate 约束，UI 用 MT/s；历史函数名 mhz 不代表 DRAM 真实 clock MHz。
CFR 另外有 667/800，但当前 ASUS allowlist 没有开放这些值，更没有 DDR4/XMP/时序编辑。

转换见 [asus_g41_policy.h](../../../src/boards/foxconn-g41mxe/coreboot-overlay/src/drivers/efi/asus_g41_policy.h)。
bridge 优先读取有效 SaSetup；不匹配布局或未知值不套用，回到 native option/fallback。
数据保存契约见 [ConfigAccess](../asus-ui/config-access.md)。

## SPD 和速率选择

get_max_mem_speed_mhz 只接受 0/667/800/1066/1333，其他值退回 Automatic。
DDR3 用 MAX(min_tCLK, cap 对应 tCK) 限制选择，仍服从 SPD 的更慢要求；
DDR2 的 667 cap 在原选择高于 667 时降低。不会为了指定上限突破 DIMM/chipset 条件。
“1333 上限”不能承诺这块 G41 在所有 FSB/DIMM 组合下均运行 1333。

## 缓存身份

修改后的 sysinfo 包含 max_mem_speed_mhz，MRC_CACHE_VERSION 从 0 升到 1。
非 S3 快速路径同时检查 SPD checksum、CPU max_fsb 和保存的 rate cap。
修改 cap 后不复用旧训练。训练缓存区见 [flash map](flash-map-variables.md)。

memory_fast_boot=0 在普通启动忽略缓存，warm reboot 会进入既有 cold-reset/retraining 路径。
S3 必须恢复原训练；不能为“关闭快速训练”破坏正在恢复的 DRAM 状态。
新训练结束才 stash data；cache 缺失、DIMM 不匹配与 S3 恢复失败不是同一个分支。

## 源码与验证边界

实现位于板级 coreboot.patch 的 x4x/raminit.c、raminit.h、raminit_ddr23.c。
POST stage 标记由 raminit_postcodes.h 保留，不能把标记出现当成电气训练质量保证。
policy 的 14 项回归同时覆盖内存和风扇转换，独立 coreboot 构建已通过。
真机 RTM 证明当前组合能启动；不同 cap、不同 DIMM 和 S3 尚未逐一验收。

源码 / 回归入口：[coreboot.patch](../../../src/boards/foxconn-g41mxe/patches/coreboot.patch) / [test_g41_policy.c](../../../tests/unit/test_g41_policy.c)。
