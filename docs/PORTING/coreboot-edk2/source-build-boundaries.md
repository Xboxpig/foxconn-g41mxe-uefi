# 独立源码组合与构建输入边界

## 所有权

src/coreboot/upstream、src/edk2/upstream是固定git revision导出的完整源码；
已有子模块以实际checkout revision导出，source-lock.json保留身份。
common patch是通用修正，board/patches是G41策略，board/coreboot-overlay与edk2-overlay是新增本板文件。
ASUS闭源模块、资源与通用HII工具单独存放，board/asus-ui保存本板allowlist和policy schema。

## 组合规则

prepare-sources.sh只改build/coreboot、build/edk2、build/seabios。
rsync --delete的目标是固定的生成目录，拒绝符号链接；flock串行化组合。
patch/overlay内容hash形成.sources-ready；上游快照按固定版本视为只读。
历史EDK文件有CRLF/LF混合，git apply --ignore-space-change只用于其context匹配；
源码保全比较允许行结束不同，不忽略代码内容。不要将build中的修改当真源。
GitHub clone具有外层.git，组合时用GIT_CEILING_DIRECTORIES将Git发现限制在build边界，
使apply按独立源码树处理；否则Git可能把upstream相对路径视为子目录之外而静默跳过。
IT8720 mode回归编译实际组合后的函数，可检测这种未应用板级patch的情况。

## 三种构建

1. --repack-only：归档v5 coreboot + 已归档v6 FD，重现同字节RTM。
2. build.sh：16线程构建SeaBIOS CSM、生成ASUS模块、构建EDK FD，再替换payload；
   不改已认可coreboot stages，输出只在build/artifacts。
3. build-coreboot.sh：使用外部FD，CONFIG_PAYLOAD_ELF，不走嵌套EDK checkout；
   复用toolchains/coreboot/xgcc与board microcode独立全量编译。
   明确传DOTCONFIG及XGCCPATH/bin（末尾slash），避免olddefconfig改了别处配置或误用系统编译器；
   关闭CONFIG_PXE，网络模块已经在外部FD，不额外clone/build Legacy ROM。

## 结果身份

本次新布局已完成EDK/CSM/UI和coreboot独立源码构建；源代码生成ROM是developer-verified，不自动继承RTM认可。
归档FD重打包的SHA256与RTM一致，证明目录变化没有改release。
旧目录39个coreboot、200个EDK修改/新增文件与组合结果保全；不git reset/checkout丢弃用户改动。
上游revision、GPL/BSD等license与闭源资源分发限制均保留。

## 本项目 harness 的第三方资料检查

原 runtime 的 credential-assignment 形状规则会命中公开密码学测试向量/API例子，
并把固定上游中的辅助Cargo/Go/Python manifest当成未锁定本板依赖。
本项目仅对src/coreboot/upstream/**和src/edk2/upstream/**设置lockfile例外，
版本仍由source-lock.json固定；本地board/patch/tool代码不在例外中。
secret-fixtures.json固定32份已核对上游文件的SHA256、72个行号和单一shape规则；
任何文件内容变化、其他行或AWS/GitHub token形状都不能复用此例外。
没有删改上游测试向量或关闭所有secret检查。

vendored harnesslib.py保留3.0.0-candidate.1基线，并增加这两个本项目scan helper；
原文件SHA256为2d53e8e037371f50c706eabb0361a635b2b254edd49556ed7854bf8b43914035。
扫描跳过根build的生成副本，不跳过src中任何维护代码；核心认可/身份/谱系检查未改。
test_harness_fixtures.py覆盖精确命中、文件变更、越界路径、非法规则/理由/行号和重复项拒绝。
此适配是治理检查工具，不属于用户已经验收的BIOS实现内容。

源码 / 回归入口：[prepare-sources.sh](../../../tools/prepare-sources.sh) / [build-coreboot.sh](../../../tools/build-coreboot.sh) / [source-lock.json](../../../source-lock.json)。
