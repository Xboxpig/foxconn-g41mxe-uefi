# DXE pool ASSERT 热点与 PcdDebugPropertyMask

## 热点证据

Core 2/Q35、4核、1GiB，匹配DxeCore加载基址0x5bcb000。
24次GDB RIP采样中19次落在0x5be1618，链为AMITSE→CoreAllocatePool→
CoreInternalAllocatePool→CoreAllocatePoolI→IsListEmpty→InternalBaseLibIsListValid。
free-list检查4,849节点、2,502页，返回表头且前后链接一致；另一bin19节点也闭环。
这些检查支持“昂贵但无观察到的损坏”，不是无限期内存正确性证明。

## 开关含义

USE_CBMEM_FOR_CONSOLE会取消MDEPKG_NDEBUG。RELEASE并不自动保证ASSERT表达式不求值。
mask03的bit0仍启用链表validation，关闭dead-loop不等于关validation。
同实例只改_gPcd_BinaryPatch_PcdDebugPropertyMask为02，后续24次热点0次；不改allocator/list算法。
正式构建保留02与CBMEM debug输出，真实EFI_STATUS guard不删。RTM verifier解析ELF符号的实际字节。

## 用户验收与限制

v4真机动画流畅，v6又确认非常流畅/RTM。采样19/24不是严格CPU百分比，未声称FPS或绝对延迟。
分配器TPL16是正常lock，不是provider高TPL泄漏。
如果复用方案时发现list异常，必须修内存破坏，不能照搬关ASSERT作为掩盖。
源代码对应EDK上游DxeCore/BaseLib，运行参数在tools/build.sh。

源码 / 回归入口：[build.sh](../../../tools/build.sh) / [verify-rtm.py](../../../tools/verify-rtm.py)。
