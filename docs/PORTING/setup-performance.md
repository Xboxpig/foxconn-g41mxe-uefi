# Setup 性能定位：技术导航

要分开处理“Entering Setup 等待 90 秒”和“进入后约 2 秒一刷”。
最终用户在 v4 与 v6 均确认流畅；没有虚构精确 FPS、固定毫秒指标或完整 SPI 重读原因。

- [BDS hook、BootManagerMenu 与 DeviceManager constructor 的三处扫描](setup-performance/bds-lazy-connect.md)
- [DXE allocator/list ASSERT 热点、03→02 对照和实际 PCD](setup-performance/dxecore-assert.md)
- [GDB symbols、CBMEM 计时、截图与缓存属性的证据边界](setup-performance/trace-and-evidence.md)

入口延后设备发现；运行时关闭昂贵 ASSERT 表达式仍保留日志和实际状态检查。
framebuffer UC/WC 是未在真机闭合的假设，不写成已证实修复。
源码 patch 与 mask 固定保留，诊断过程脚本/log 不作为日常构建依赖。
