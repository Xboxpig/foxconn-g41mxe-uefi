# RTM1 验证摘要

本文件是对真实已有结果的归档摘要，不是未运行测试的预期输出。原过程日志按用户要求移出工作目录。

## 固件与硬件

- RTM 是已写入 v6 的相同字节；SHA256 `24567d0a88a38d6dc592263e169e177d9fdd39bda39b92a79e5fd25060e8aa83`。
- CH341A / W25Q128.V，flashrom `-w <v6> -n`，exit 0，`Erase/write done from 0 to ffffff`。
- 没有单独预清零、备份、写后验证。旧内容的内部读取与必要扇区擦除属于 flashrom 写入流程。
- 用户随后明确“这一版非常流畅，我认为可以作为RTM”。前序版本亦有“感应器也预期工作”的反馈。
- 这些反馈不代替真机 Legacy 启动和每一个 settings consumer 的专项验证。

## 软件验证

- Q35 / Core 2 / 4 cores：真实 MBR 的 `NATIVE_CSM_INT10_PASS`、`NATIVE_CSM_INT13_LBA_PASS`、
  `NATIVE_CSM_PIC_TIMER_PASS`。路径为 UEFI Boot Manager → LegacyBoot → INT19 → 0000:7c00。
- disabled CSM 构建正常进入 ASUS，未安装 legacy platform protocols。
- ASUS Boot 控件 F10 保存 `csm_enable=1`、`boot_device_control=1` 均 Success；该 GUI 测试为诊断 Q35/EMU，
  不证明 SPI 持久化。
- ConfigAccess 原生 CSM 配置 56 cases、policy modes/error inputs、v5 allowlist、v6 question IDs、
  donor hash 拒绝、IT8720F 1536 mode 转换、provider 与 fan/memory policy 回归已通过。
- ROM verifier：16 MiB，非 payload 命名 CBFS 文件等同 v5，MRC/SMMSTORE/FMAP 保持；payload 解压等同
  归档 FD；原生 CSM/PIC/Video 模块及 P10 VBIOS 存在，诊断 app 不存在，DxeCore 实际 mask=02。

## 性能证据

90 秒进入阶段修正覆盖三处全局设备扫描；原生 UI 的 Device Manager constructor 也在共用路径中。
Q35 24 次 GDB 采样有 19 次落在 pool ASSERT 链表检查，检查列表一致；同实例 mask03→02 后 0/24。
这些数字不是精确 CPU 占比。v4 和 v6 真机流畅性得到用户明确反馈；没有虚构精确 FPS/毫秒阈值。

## 本次目录整理

2026-10-01，新布局的实际验证：

- 旧目录 39 个 coreboot 与 200 个 EDK 修改/新增文件同组合树一致；只允许 CRLF/LF 差异。
- bash tools/test.sh 全部通过：真实 provider、policy、ConfigAccess、HII/PE/hash 与 ROM verifier。
- bash tools/build.sh 完成 CSM16、UI 模块、BaseTools 和 EDK II RELEASE 源码构建；16线程。
  该开发 ROM SHA256 为 2514e7ee0faab314d5cb0aa45e84d3a2844c7d8ad20ca5a3df1fea291b10d95f，
  不是已认可镜像，未刷入。
- bash tools/build.sh --repack-only 与已认可 RTM cmp 完全相同。
- bash tools/build-coreboot.sh 使用本地 i386-elf/iasl、显式 DOTCONFIG/XGCCPATH 和外部 FD，
  独立全量源码构建通过，不执行嵌套 EDK/PXE 下载构建。
- 四个维护 shell 入口通过 bash -n；harness fixture gate 的8项测试通过，含对应非法输入拒绝。
- 技术记录拆为六个主题导航和29篇细节，覆盖寄存器/ABI/变量布局/consumer/模拟边界。

重排不改变 RTM 字节。重编译生成物仍属于 developer-verified，不自动继承用户对 RTM 的认可。
原芯片备份和原厂 MOD 16MiB 恢复镜像保留在 backups；过程脚本/log、诊断镜像和旧构建树
已移入回收站，不覆盖 releases；回收站未清空前可以恢复。
最终 harness check exit0、ok=true、valid=true，0 errors / 0 warnings。
已认可基线通过 dry-run 后登记为 current，只绑定原样 RTM ROM 和用户真实启动/UI反馈。
