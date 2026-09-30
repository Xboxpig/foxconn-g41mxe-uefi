# Foxconn G41MXE DIY UEFI — RTM1

适用于 Foxconn G41MXE rev 1.0、Intel G41/X4x + ICH7、IT8720F、771 改装 Xeon X5450，
SPI 为 W25Q128 16 MiB。基于 coreboot + EDK II，使用移植的 ASUS AMITSE 图形界面。

用户在刷入 v6 后确认“这一版非常流畅，我认为可以作为 RTM”。RTM1 是该镜像的原样归档，
仅改文件名，不重编译、不改字节。本次整理没有再次刷写硬件。

## GitHub 与下载

仓库：[Xboxpig/foxconn-g41mxe-uefi](https://github.com/Xboxpig/foxconn-g41mxe-uefi)。
RTM 下载入口：[RTM1](https://github.com/Xboxpig/foxconn-g41mxe-uefi/releases/tag/rtm1)。
源码、patch/overlay、29 篇技术记录、ASUS donor/资源和 RTM 镜像一并保存。
ASUS/AMI 等闭源模块保留原有权利，不因公开上传而变成开源或获得重新授权；详见[许可证说明](docs/LICENSING.md)。
项目非 ASUS/Foxconn 官方固件；刷写须自行核对主板和芯片，并保留可用编程器与恢复备份。

```sh
git clone https://github.com/Xboxpig/foxconn-g41mxe-uefi.git
cd foxconn-g41mxe-uefi
python3 -m pip install PyYAML pyelftools
python3 tools/verify-rtm.py
```

上游源码及当时已初始化子模块均作为固定文件快照保存，直接 clone 后不需要递归下载这些源码。
本机芯片备份、凭据、构建缓存、Python 环境和已有交叉编译器不在公开仓库中。
需要治理 CLI 时，先创建本地 .harness/venv 并安装 .harness/runtime/requirements.lock 中所需依赖；
一般 check 只需 PyYAML，语义检索额外依赖按固定 manifest 准备，不会自动下载模型。

## 使用与边界

- 成品：[g41mxe-rtm1-16m.rom](releases/g41mxe-rtm1/g41mxe-rtm1-16m.rom)，16,777,216 bytes。
- SHA256：`24567d0a88a38d6dc592263e169e177d9fdd39bda39b92a79e5fd25060e8aa83`。
- 默认关闭 CSM 时，无可用默认 UEFI 启动项进入 ASUS UI；Shell、iPXE 是手动工具。
- CPU、内存、北桥、南桥和风扇设置只保留已接入本地 consumer 的项目，保存后重启应用。
- CSM 默认关闭。Boot → Launch CSM → Enabled；Boot Device Control 可选混合、UEFI only 或 Legacy only。
- 原生 CSM 已通过 Q35 MBR/INT10/INT13/PIC 测试。RTM 认可确认真机启动与 UI 流畅，
  不代表已经验证真机 Legacy 磁盘、独显、Legacy USB/PXE、所有旧系统或所有设置效果。
- 没有手动 PLL/FSB、CPU 电压、内存时序超频；ICH7 没有 AHCI/RAID。未实现 Secure Boot。
- 整片烧录会使用镜像中的初始 SMMSTORE，重置原启动项和已保存设置。仅适用这块已确认的主板，不能刷到 Z490 或其他 G41 主板。

## 源码布局

```text
src/
  coreboot/                   上游源码快照 + 共用 patch
  edk2/                       上游源码快照 + 共用 patch + 历史 CSM / SeaBIOS / iPXE
  asus-ui/                    闭源 donor 资源、通用 HII 工具、UI 资源 overlay
  boards/foxconn-g41mxe/       本板 patch、coreboot/EDK overlay、UI policy、Linux 工具、配置
tools/                        可维护的组合、构建与验证入口（不含烧录入口）
tests/                        保留的实际源码回归与 MBR 测试源码
toolchains/coreboot/          复用本机已有交叉编译器，避免重新下载
releases/g41mxe-rtm1/          不可变 RTM、校验信息、必要重建输入与验收记录
docs/                         分主题记录 + harness SPEC/RELEASE 导航
backups/                      原芯片备份与恢复镜像；不属于可删除构建缓存
build/                        生成物；不是源码真源，可移入回收站后重建
```

coreboot 不再包含 EDK II checkout。源码中的本板改动以 patch/overlay 单独保存；
只有 `tools/prepare-sources.sh` 在 build 内组合它们。不要在 build 内维护修改。
固定版本与实际已使用的子模块 revision 见 [source-lock.json](source-lock.json)。
ASUS 原始模块是闭源二进制，本项目保存的是移植工具和本地兼容层源码，不宣称拥有 ASUS 源码。
上面的 toolchains 和 backups 是本机目录，已被 Git 忽略，不随公开仓库上传。

## 构建和检查

复用已存在的本地依赖，不要求访问网络；编译固定使用 16 线程。需要 Bash、rsync、Git、make、
GCC、Python（PyYAML、pyelftools）及已有 coreboot 交叉编译器；EDK II 用本机 GCC。
新 clone 的 coreboot 全量构建需自行准备兼容的 i386-elf GCC/GNAT、iasl/nasm 于
toolchains/coreboot/xgcc/bin；RTM 校验、归档 FD 重打包及 EDK II payload 构建不依赖这份本机工具目录。

```sh
bash tools/test.sh
bash tools/build.sh --repack-only    # 使用已归档 FD，重建字节相同的 RTM
bash tools/build.sh                  # 从拆分源码重建 CSM16、ASUS UI、EDK payload，再组合 ROM
bash tools/build-coreboot.sh         # 可选：coreboot 独立全量重编译，消费外部 FD
```

默认输出在 `build/artifacts/g41mxe-rebuilt-16m.rom`，绝不覆盖 releases 内的 RTM。
全量源码重编译可能因构建路径、时间和版本字符串而不同，不能仅因“编译成功”晋级为已验收 RTM。
源码变化会触发 build 源码重新组合；开始组合前请先结束使用同一 build 的编译。

## 技术记录

总入口：[29 篇技术细节索引](docs/PORTING/README.md)。以下六个主题页只做导航，
寄存器、变量布局、ABI、构建和测试边界分别记录，不再堆在一篇移植流水账里。

- [ASUS UI 移植](docs/PORTING/asus-ui.md)
- [coreboot + EDK II 平台适配](docs/PORTING/coreboot-edk2.md)
- [Entering Setup 延迟与 UI 卡顿优化](docs/PORTING/setup-performance.md)
- [Linux 传感器采集与验证方法](docs/PORTING/linux-sensors.md)
- [G41MXE / IT8720F 驱动和通道映射](docs/PORTING/g41mxe-it8720f.md)
- [原生 UEFI CSM](docs/PORTING/native-csm.md)
- [已认可 RTM 基线契约](docs/RELEASE/p-rtm1-baseline.md) / [实现清单与验收边界](docs/RELEASE/rtm1.md)
- [验证摘要](releases/g41mxe-rtm1/evidence/validation.md)
- [来源与许可证](docs/LICENSING.md)

## Harness

按用户要求初始化 harness-project-governance。关系、状态与验收证据由 `.harness/records.yaml` 管理，
Markdown 保存原文。技术记录登记为工程资料，不因整理自动成为所有硬件行为的正式验收契约。

```sh
.harness/venv/bin/python .harness/runtime/harness.py --root . check
.harness/venv/bin/python .harness/runtime/harness.py --root . catalog --scope current --scope legacy
```

语义模型没有为本次整理额外下载；需要检索时可显式使用 `search ... --lexical-fallback`。
本机过程脚本、日志、诊断 ROM 和旧 build 经保全后移入回收站；回收站未清空前仍可恢复。
已认可 SPEC/RELEASE 中的“尚未公开发布”是基线登记时的分发状态；后续 GitHub 分发事件
单独记录在 releases/g41mxe-rtm1/evidence/publication.md，不回写已认可契约或扩大验收范围。
