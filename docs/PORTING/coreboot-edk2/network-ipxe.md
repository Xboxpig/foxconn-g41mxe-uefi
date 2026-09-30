# 内嵌 UEFI iPXE：模块与启动边界

## 实际集成方式

RTM 的 NETWORK_IPXE=TRUE 将 X64 ipxe.efi 纳入 EDK FV，
由 PcdiPXEFile/PlatformRegisterFvBootOption 注册名为 iPXE Network Boot 的入口。
固定源码 snapshot 在 src/edk2/network/ipxe，
当前已用二进制在 board/edk2-overlay/UefiPayloadPkg/NetworkDrivers/ipxe.efi。
这不是在 G41 legacy BIOS 内模拟 UEFI，也不是把 Legacy PXE ROM 当作 CSM PXE。

## 构建的复用边界

tools/build.sh 重建 EDK 时复用归档 ipxe.efi；不承诺同时从 iPXE 源码重建它。
tools/build-coreboot.sh 使用外部 FD，因此关闭 CONFIG_PXE，防止上游嵌套规则
因 EDK config 被关闭而自动改建另一种 Legacy ROM、执行 clone/checkout。
网络模块在 FD 中仍存在；RTM CBFS 本来没有额外 pci10ec,8168.rom。
iPXE 源码 revision 在 source-lock.json，可独立研究，不作为偷偷换网络二进制的构建步骤。

## 使用和限制

Shell/iPXE 均为手动 CATEGORY_APP；缺 OS entry 默认进入 ASUS，不立即发起网络请求。
RTL8111/8168 板载路径、LAN enable 与网络线/DHCP/服务器配置都影响成功；
入口存在不等于某一 PXE server 已被真实启动过。
Q35 不能替代本板 RTL 驱动和实际 DHCP/TFTP/HTTP 验收。
本次没有再次接入网络启动服务器，也没有把 UEFI iPXE 记成已验证 Legacy PXE。

源码 / 回归入口：[ipxe.efi](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/NetworkDrivers/ipxe.efi) / [build.sh](../../../tools/build.sh)。
