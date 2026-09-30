# ConfigAccess buffer、NV 变量与保存边界

## 存储身份

源码 G41HiiConfig.c、G41NativeOptions.h，均属于 G41MXE board/edk2-overlay。
G41PlatformData GUID FB3DCA8B-EAB5-4C93-9900-5247A7211886 仅用于 HII route；
真正 UINT32 变量使用 coreboot NV GUID CEAE4C1D-335B-4685-A4A0-FC4A94EEA085。

| Buffer | 约束 |
| --- | --- |
| G41PlatformData | 16 bytes；13 个有效字段，剩余 reserved 必须 0 |
| SaSetup | 1282 bytes；只允许 offset18e 的 UINT16 0/1067/1333 |
| AsusQFanSetupData | 144 bytes；只接受 offsets0/8/18/20 的已审计控制/预设 |
| Timeout | UINT16 |
| BootOrder | UINT16 启动项数组，使用实际大小，保持已有成员 |

## Route 的顺序

FindStore → ReadStore → ConfigToBlock → 验证全部字段与 reserved → 预检查变化及 NV attributes →
仅 SetVariable 变化字段。非法值不得已经写了一部分后才发现。
接受 NV|BS 或 NV|BS|RT，并保留已存在的属性；其他属性拒绝 EFI_WRITE_PROTECTED。
变量缺失用 safe default，数据长度/值域错误不能直接当有效设置。

## 重要限制

预检查不是多变量事务：SetVariable 中途失败时返回错误，之前已成功的变化不自动回滚。
不能在文档中写成“所有设置原子保存”。Route 保存只是存储成功，硬件消费者通常在 reset 后执行。
BootOrder 的单项选择只把已有 entry 移到首位；整数组 route 需为原 entries 的 permutation，
不默默删除、重复或创建启动项。BootNext/全部有效 OS 项仍不因一次 F10 测试而算完整验收。

## 复现与证据

bash tools/test.sh 编译真实 G41HiiConfig.c，56 cases 覆盖 defaults、所有允许值、UINT32 存储、
reserved/非法值、属性保留和写失败。host harness 丢弃未调用的 EFI 安装函数，不能冒称 InstallProtocol
真机测试。Q35 UI F10 保存返回 Success 不证明 SMMSTORE 在真实 reset 后仍保留数据。

源码 / 回归入口：[G41HiiConfig.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusSetupHiiDxe/G41HiiConfig.c) / [test_g41_native_config.c](../../../tests/unit/test_g41_native_config.c)。
