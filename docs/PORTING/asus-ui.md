# ASUS UI 移植：技术导航

本主题记录 PRIME Z490-A 3401 的原厂 AMITSE/资源移植；不是重绘，不执行 Z490 Setup 硬件回调。
闭源 donor、通用 HII 工具与 G41 专属 bridge/allowlist 分开保存。

- [Donor 模块、FV 文件和协议 GUID / ABI](asus-ui/donor-and-fv.md)
- [HII/IFR、VarStore、原厂 form/QID 导航](asus-ui/hii-import-navigation.md)
- [ConfigAccess、UINT32 NV 保存、属性和非事务边界](asus-ui/config-access.md)
- [精确 hash、RVA、PE section 与 hardware-safe patch](asus-ui/binary-patching.md)
- [N/A sentinel、HII 定时更新和多消费者格式化 ABI](asus-ui/display-refresh.md)

源码入口：src/asus-ui 与 src/boards/foxconn-g41mxe/asus-ui、edk2-overlay。
输入不是任意版本的 ASUS CAP；patch hash guard 必须保留。用户确认本版真机流畅，
不代表已验证所有 donor 隐藏路径或取得公开分发许可。
