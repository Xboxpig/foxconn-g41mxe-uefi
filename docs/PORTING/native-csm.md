# 原生 UEFI CSM：技术导航

实现为 LegacyBiosDxe → real-mode thunk → SeaBIOS Csm16，BBS 项与 UEFI 共用 Boot Manager，
不是重启切换 SeaBIOS payload。默认关闭 CSM，保持快速 UEFI Setup 路径。

- [Framework 组件、平台 driver、volatile policy 与 BootAllowed](native-csm/platform-policy.md)
- [IVT/BDA page0、PAM map、FarCall shadow 权限恢复](native-csm/low-memory-pam-thunk.md)
- [PIC、PIRQ/ELCR、RCBA 和 bridge swizzling](native-csm/pic-pirq-routing.md)
- [P10 VBIOS metadata、BBS/INT19 和三项 MBR 可执行测试](native-csm/vbios-bbs-tests.md)
- [ASUS CSM 控件的 HII 与 NV 保存](asus-ui/config-access.md)

Q35 的 INT10/INT13/PIC 真实执行已通过。RTM 用户反馈确认真机启动/UI 流畅，
尚不能替代真实 GMA/Legacy disk/独显/Legacy USB/PXE/具体旧 OS 的专项验收。
