# G41MXE RTM 项目入口

项目定义状态由 `.harness/records.yaml` 管理。正式范围读 `docs/SPEC/README.md`、
`docs/RELEASE/README.md`；技术事实和经验在 `docs/PORTING/`，不自动当作全部硬件验收。

## 源码所有权

- `src/coreboot/upstream`、`src/edk2/upstream` 是固定上游快照；共用修改写独立 patches。
- `src/asus-ui` 只含 UI 资源/通用工具，闭源 donor 不称为 ASUS 源码。
- G41MXE 的寄存器、策略、驱动、UI allowlist、板级补丁一律在 `src/boards/foxconn-g41mxe`。
- build 是组合后的生成物，不在其中维护源代码。releases 内已认可 RTM 禁止覆盖。
- 目录移动不能改变 RTM 哈希或把未验收能力记成 accepted。烧录需当前用户明确授权。

## 执行规则

保留现有未提交修改；使用 apply_patch 编辑。仅用户明确要求时使用 Graphify 或分派 subagent。
构建用 16 线程，复用已存在依赖；下载/换源遵守用户 TUNA/已验证国内镜像及代理规则，
代理下载计划超过 500 MB 先询问。Docker 镜像不删除；备份和 toolchain 不当作过程缓存清理。

## 验证入口

`bash tools/test.sh`；`bash tools/build.sh --repack-only`；源码重建为 `bash tools/build.sh`。
coreboot 独立全量构建为 `bash tools/build-coreboot.sh`。结果满足请求后结束，不擅自扩功能。
治理检查：`.harness/venv/bin/python .harness/runtime/harness.py --root . check`。
晋级先 dry-run；只有真实 E2E 和用户明确认可才使用 --user-acknowledged。
