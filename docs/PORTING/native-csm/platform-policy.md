# LegacyBios 服务、平台 driver 与本次 boot 策略

## 原生服务

历史LegacyBiosDxe安装Framework LegacyBios协议；Csm16从RAW FV载入，
real-mode thunk与UEFI Boot Manager直接连接。与独立SeaBIOS payload切换不同。
IntelFrameworkPkg/LegacyBootManagerLib/8259/BiosVideo来源固定为edk2-stable201808。

## Platform entry

G41CsmSupportEntry只接受host/LPC=2e308086/27b88086或Q35诊断29c08086/29188086。
读csm_enable(UINT32,0..1)，boot_device_control(0..2)。
本boot policy=enabled ? 1 | (control<<8) : 0，写volatile BS变量G41CsmActivePolicy。
只接受0/1/101/201（十六进制）；missing/malformed回0。
disabled不安装legacy platform/PIC服务；enabled依次LegacyRegion、LegacyInterrupt、LegacyBiosPlatform，
任何关键错误直接返回。

## 启动过滤

G41CsmBootAllowed检查BBS_DEVICE_PATH/BBS_BBS_DP：
policy1混合；101允许UEFI、拒Legacy；201允许Legacy、拒普通UEFI OS。
MEDIA_PIWG_FW_FILE或CATEGORY_APP是手动工具豁免，Setup/Shell不会因Legacy-only无法使用。
策略本次boot锁定，菜单F10保存后reset才生效，不是边调一半PIC一半UEFI。

## 证据

test_csm_policy覆盖modes、malformed/default/tool exemption；Q35确认disabled正常ASUS和无legacy平台协议。
RTM未编G41_CSM_TEST诊断app。EfiBootManagerBoot实际应用过滤，不只是菜单文字。
CSM与Secure Boot不同，本构建不实现Secure Boot；iPXE仍为UEFI。

源码 / 回归入口：[G41CsmSupport.c](../../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/G41CsmSupportDxe/G41CsmSupport.c) / [G41CsmPolicy.h](../../../src/boards/foxconn-g41mxe/edk2-overlay/MdeModulePkg/Include/Library/G41CsmPolicy.h) / [test_csm_policy.c](../../../tests/unit/test_csm_policy.c)。
