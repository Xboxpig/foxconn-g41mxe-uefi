# SPI flash map、CBFS 与 SMMSTORE

## 固定布局

W25Q128 为128 Mbit =16 MiB。RW_MRC_CACHE offset800000 size10000，
SMMSTORE offset810000 size80000，COREBOOT offset891000。
ROM 的前0x891000以及所有非payload命名CBFS文件，RTM v6与保留的v5一致。
最终压缩payload 4,101,949 bytes；原始FD 20,971,520 bytes解压到RAM，
FD大小不等于SPI文件大小，也不需要在每次进入Setup时重新解压一遍。

## 状态与写入

MRC保存训练缓存，SMMSTORE保存Boot####和设置，两者不是页面资源。
NV变量由EDK的变量驱动管理和缓存，不把GetVariable读数等同完整SPI扫描。
空白变量区首次格式化、变量驱动未就绪、正常再次进入Setup，是三个不同场景。
整片刷ROM会用归档的初始变量区，丢失原保存项。RTM的快速写入按用户要求未做回读验证；
flashrom内部读取旧内容和擦除必要sector不等同备份或写后校验。

## 复现

tools/verify-rtm.py检查实际CBFS/FV、LZMA payload和归档FD，不只检查外部manifest。
coreboot-v5-base.rom作为精确原型保留，--repack-only删除旧payload后添加已归档FD，结果可逐字节等同RTM。
新源码构建时间/路径变化会改变FD身份；不覆盖已认可release。真机16MiB启动已成功，
但不能据此为其他ICH7板或其他flash descriptor布局作寻址保证。

源码 / 回归入口：[verify-rtm.py](../../../tools/verify-rtm.py) / [build.sh](../../../tools/build.sh)。
