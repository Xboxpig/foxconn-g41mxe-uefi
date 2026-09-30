/* Generated from g41_native_settings.json; do not edit. */
#define G41_PLATFORM_BUFFER_SIZE 16
#define G41_PLATFORM_GUID {0xfb3dca8b,0xeab5,0x4c93,{0x99,0x00,0x52,0x47,0xa7,0x21,0x18,0x86}}
STATIC G41_NATIVE_OPTION mNativeOptions[] = {
  {L"eist", 1, 0x0003},
  {L"vmx", 1, 0x0003},
  {L"gfx_uma_size", 6, 0x1fc0},
  {L"sata_mode", 2, 0x0006},
  {L"pata_controller", 1, 0x0003},
  {L"hd_audio", 1, 0x0003},
  {L"onboard_lan", 1, 0x0003},
  {L"power_on_after_fail", 0, 0x0003},
  {L"post_success_beep", 1, 0x0003},
  {L"nmi", 0, 0x0003},
  {L"memory_fast_boot", 1, 0x0003},
#ifdef G41_NATIVE_CSM
  {L"csm_enable", 0, 0x0003},
  {L"boot_device_control", 0, 0x0007},
#endif
};
