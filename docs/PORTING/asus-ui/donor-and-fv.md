# Donor 模块、FV 文件与协议 ABI

## 范围与输入

使用 PRIME Z490-A 3401。原始 CAP 在 src/asus-ui/assets/donor，配套 PE32/资源在
src/asus-ui/edk2-overlay/UefiPayloadPkg/AsusAmitseBinary。文件 GUID 是 FV 定位键，
协议 GUID 是 LocateProtocol 定位键，二者不能混为一谈。

| 用途 | FV 文件 GUID / 协议 GUID |
| --- | --- |
| AMITSE 执行文件 | B1DA0ADF-4F77-4070-A88E-BFFE1C60529A |
| Setup RAW 数据 | 6F7C8B8F-0F64-4BAA-95EE-06F749D73E9B |
| AMITSESetupData | FE612B72-203C-47B1-8560-A66D946EB371 |
| Resource Loader | 文件 5C0FB3B9-F7BB-467B-A4DC-89D7D5A58432；协议 DE97C321-8C29-4AA7-8543-18F4C3949A18 |
| 资源 archive | CC5840D2-D8EA-459E-BAF4-349AC710EBBE |
| SPD Transfer | 文件 7A54B36F-F745-462C-B11F-16E03E52B617；协议 2B1A35EE-E799-40B4-A7BB-B3EA3535D1C7 |
| Mouse | C7A7030C-C3D8-45EE-BED9-5D9E76762953 |

## 本地兼容协议

AsusAmiCompatDxe.c 安装：
0903DD14-2CA0-458A-B5EB-0C0CA30D785C（14 项 method table）；
20E28787-DF32-4BDA-B7E7-CBBDA3371EF8（4 项 OCMR table）；
A45414BA-0172-4283-9A1D-A7B77177BF29（AI availability，明确 FALSE）。
这些 shim 只覆盖已审计的调用形状，no-op 成功不能当成 OCMR/AI 硬件真实存在。
HWM 协议 78039142-4378-48EF-BB5D-F63BF2C5DEB5 由本板 G41Sensors 提供，不执行原 Z490 HWM 驱动。

## 执行边界与复现

ASUS_SETUP_HII_DATA_ONLY=TRUE：Setup 放 RAW，不调其入口；CmosDxe 和 donor SMBIOS 的执行支路不启用。
FDF 中旧 LAB/QEMU-only 名称是历史命名，是否执行必须核对当前宏和实际 FV，
不能凭注释认定 RTM 是 QEMU 配置。主板硬件访问仍由 G41 ID gate 和本地 consumer 控制。
源依据：board/patches/edk2.patch 的 FDF，board/edk2-overlay 的 AsusAmiCompatDxe.c/.inf。
验证用 ROM verifier 检查实际模块，UI 启动检查协议依赖；不能把“协议能定位”当成所有调用语义均完成。

源码 / 回归入口：[AsusAmiCompatDxe.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusAmiCompatDxe/AsusAmiCompatDxe.c) / [edk2.patch](../../../src/boards/foxconn-g41mxe/patches/edk2.patch)。
