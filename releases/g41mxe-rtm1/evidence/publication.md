# RTM1 GitHub 公开分发记录

## 分发事件

2026-10-01（Asia/Shanghai），按本会话用户“完成之后就上传到我的 github，公开仓库”
及随后“都公开”的明确授权，公开源码、文档、ASUS/AMI donor 与资源、RTM ROM 及必要重建输入。

- 仓库：[Xboxpig/foxconn-g41mxe-uefi](https://github.com/Xboxpig/foxconn-g41mxe-uefi)。
- Release：[G41MXE RTM1](https://github.com/Xboxpig/foxconn-g41mxe-uefi/releases/tag/rtm1)。
- 初始交付提交及 `rtm1` tag：`8a0af141eb237be1aa8d0060a489b248f8b418a8`。
- Release 发布时间：`2026-09-30T18:00:22Z`，即北京时间 2026-10-01 02:00:22。
- GitHub API 确认仓库 `private=false`，Release `draft=false`、`prerelease=false`。

本记录是实际分发事件，不是新的硬件验收，不改变已认可 SPEC/RELEASE 或其验收范围。
后续发布记录与导航修正单独提交；RTM tag 和 ROM 字节保持不变。

## 镜像身份与公开下载验证

- 文件：`g41mxe-rtm1-16m.rom`，16,777,216 bytes。
- SHA256：`24567d0a88a38d6dc592263e169e177d9fdd39bda39b92a79e5fd25060e8aa83`。
- Release 附件包含上述 ROM 和 `SHA256SUMS`，API 状态均为 `uploaded`。
- GitHub 返回的 ROM asset digest 与上述 SHA256 相同。
- 不带 GitHub 身份凭据，从公开下载链接取回两个附件：`sha256sum -c SHA256SUMS` 通过，
  下载 ROM 与本机已认可 RTM 执行 `cmp` 无差异。

本次未重编译或覆盖已认可 ROM，未连接主板、执行烧录或修改硬件寄存器。

## 仓库可用性验证

初始提交的干净本地 clone，仅使用仓库文件及已安装的系统依赖，实际完成：

- `bash tools/test.sh`：全部通过，包括 harness fixture、HII/PE/hash、CSM、传感器、
  policy、ConfigAccess 及 RTM verifier。
- `bash tools/build.sh --repack-only`：完成；输出与已认可 RTM 逐字节一致。
- 项目 harness `check`：exit 0、`ok=true`、`valid=true`，0 errors / 0 warnings。
- Git index 中未包含 `backups`、`toolchains`、`.harness/venv`、`build`、`work` 或 `outputs`；
  已检查没有超过 GitHub 100 MiB 单文件限制的提交文件。

这些检查证明公开内容能完成相应软件回归与归档 FD 重打包，不替代真实硬件专项验收，
也不承诺任意系统工具链下全量源码重编译具有字节可复现性。

## 权利与本机保留内容

ASUS/AMI、microcode、VBIOS 等二进制保留原有权利；用户的公开上传授权不构成厂商重新授权，
也不将这些文件变成开源源码。各开源项目的原有 LICENSE/SPDX/copyright 随源码保留，
详见[来源与许可证](../../../docs/LICENSING.md)。

原芯片备份、恢复镜像、凭据、交叉编译器、Python 环境与可重建缓存保留在本机或被忽略，
未上传。此次临时 clone、下载验证副本和生成 build 移入回收站，不覆盖源码或 RTM；
回收站未清空前可恢复。
