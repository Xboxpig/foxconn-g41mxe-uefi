#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define G41_SENSORS_HOST_TEST
#define STATIC static
#define CONST const
#define VOID void
#define EFIAPI
#define EFI_NATIVE_INTERFACE 0
#define TPL_HIGH_LEVEL 31
#define DEBUG(x) ((void)0)
#define PCI_LIB_ADDRESS(b,d,f,r) (((d) << 8) | (r))
typedef uint8_t UINT8;
typedef uint16_t UINT16;
typedef uint32_t UINT32;
typedef uint64_t UINT64;
typedef uintptr_t UINTN;
typedef UINTN EFI_STATUS;
typedef UINTN EFI_TPL;
typedef void *EFI_HANDLE;
typedef struct { UINT32 a; UINT16 b,c; UINT8 d[8]; } EFI_GUID;
static UINT8 ec[256], config[256], ec_index, sio_index;
static unsigned io_count, is_g41;
static unsigned unstable_high_reads, high_reads, raised, restored;
static UINT64 ticks;
static UINT32 cpu_signature = 0x10676;
static UINT64 fsb_msr = 0x804, perf_msr = 0x920092006000920ULL;
static unsigned msr_reads;
static UINT32 mchbar = 0xfed14001, mchbar_high;
static UINT8 mem_clock = 0x44, mem_type = 4, mem_mode = 16;
static UINT16 mem_ch0 = 32, mem_ch1;
static unsigned mmio_reads;
static UINT8 MmioRead8(UINTN address) {
    ++mmio_reads;
    switch (address) {
    case 0xfed14c00: return mem_clock;
    case 0xfed141a8: return mem_type;
    case 0xfed14111: return mem_mode;
    default: assert(0); return 0;
    }
}
static UINT16 MmioRead16(UINTN address) {
    ++mmio_reads;
    assert(address == 0xfed14206 || address == 0xfed14606);
    return address == 0xfed14206 ? mem_ch0 : mem_ch1;
}
static void AsmCpuid(UINT32 leaf, UINT32 *a, UINT32 *b, UINT32 *c, UINT32 *d) {
    assert(leaf <= 1);
    if (a) *a = leaf ? cpu_signature : 0xa;
    if (b) *b = 0x756e6547;
    if (c) *c = 0x6c65746e;
    if (d) *d = 0x49656e69;
}
static UINT64 AsmReadMsr64(UINT32 index) {
    ++msr_reads;
    assert(index == 0xcd || index == 0x198);
    return index == 0xcd ? fsb_msr : perf_msr;
}
static UINT64 GetPerformanceCounter(void) { return ticks; }
static UINT64 GetPerformanceCounterProperties(UINT64 *start, UINT64 *end) {
    *start = 0; *end = 0xffffff; return 3579545;
}
static UINT64 GetTimeInNanoSecond(UINT64 elapsed) { return elapsed * 1000000000ULL / 3579545; }
static UINT32 PciRead32(UINTN address) {
    if (address == 0x48) return mchbar;
    if (address == 0x4c) return mchbar_high;
    return is_g41 ? (address ? 0x27b88086 : 0x2e308086) : 0x29c08086;
}
static void IoWrite8(UINTN port, UINT8 value) {
    io_count++;
    if (port == 0xa15) ec_index = value;
    else if (port == 0x2e) sio_index = value;
    else if (port == 0x2f) config[sio_index] = value;
    else assert(0);
}
static UINT8 IoRead8(UINTN port) {
    io_count++;
    if (port == 0xa16) {
        if (ec_index == 0x19) {
            high_reads++;
            if (unstable_high_reads) {
                unstable_high_reads--;
                return (UINT8)high_reads;
            }
        }
        return ec[ec_index];
    }
    assert(port == 0x2f);
    return config[sio_index];
}
static EFI_TPL Raise(EFI_TPL tpl) { assert(tpl == 31); raised++; return 4; }
static void Restore(EFI_TPL tpl) { assert(tpl == 4); restored++; }
static EFI_STATUS Install(EFI_HANDLE *h, EFI_GUID *g, int type, void *p) {
    (void)h; (void)g; (void)type; assert(p); return 0;
}
static struct {
    EFI_TPL (*RaiseTPL)(EFI_TPL);
    void (*RestoreTPL)(EFI_TPL);
    EFI_STATUS (*InstallProtocolInterface)(EFI_HANDLE *, EFI_GUID *, int, void *);
} services = {Raise, Restore, Install}, *gBS = &services;
#include "../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusAmiCompatDxe/G41Sensors.c"

int main(void) {
    assert(G41InstallSensors() == 0 && mEcBase == 0 && io_count == 0);
    assert(ReadAsusSensor(0x1fb3) == 0 && io_count == 0);
    assert(ReadAsusSensor(0x9fb3) == 0x7fff && io_count == 0);
    assert(ReadAsusSensor(0xf000) == 0x7fff && msr_reads == 0);
    assert(ReadAsusSensor(0xf003) == 0x7fff && mmio_reads == 0);
    is_g41 = 1;
    config[0x20] = 0x87; config[0x21] = 0x20;
    config[7] = 6; config[0x30] = 1;
    config[0x60] = 0x0a; config[0x61] = 0x10;
    ec[0x58] = 0x90; ec[0] = 1; ec[0x51] = 0x11;
    assert(G41InstallSensors() == 0 && mEcBase == 0xa10 && config[7] == 6);
    assert(ReadAsusSensor(0xf003) == 1067);
    assert(ReadAsusSensor(0xf004) == 2048);
    assert(ReadAsusSensor(0xf005) == 3);
    for (unsigned code = 0; code < 8; code++) {
        const unsigned rates[] = {400, 533, 667, 800, 1067, 1333, 0x7fff, 0x7fff};
        mem_clock = code << 4;
        assert(ReadAsusSensor(0xf003) == rates[code]);
    }
    mem_clock = 0x44;
    mem_mode |= 2;
    assert(ReadAsusSensor(0xf004) == 0x7fff);
    mem_mode = 16; mem_ch0 = 0;
    assert(ReadAsusSensor(0xf004) == 0x7fff);
    mem_ch0 = 0xffff;
    assert(ReadAsusSensor(0xf004) == 0x7fff);
    mem_ch0 = 32;
    unsigned before_mmio = mmio_reads;
    mchbar = 0xfed14000;
    assert(ReadAsusSensor(0xf003) == 0x7fff && mmio_reads == before_mmio);
    mchbar = 0xfed14001; mchbar_high = 1;
    assert(ReadAsusSensor(0xf004) == 0x7fff && mmio_reads == before_mmio);
    mchbar_high = 0;
    assert(ReadAsusSensor(0xf000) == 3000);
    assert(ReadAsusSensor(0xf001) == 3330033);
    assert(ReadAsusSensor(0xf002) == 9);
    perf_msr = 0x620;
    assert(ReadAsusSensor(0xf000) == 2000 && ReadAsusSensor(0xf002) == 6);
    perf_msr = 0x4920;
    assert(ReadAsusSensor(0xf000) == 0x7fff);
    perf_msr = 0x8920;
    assert(ReadAsusSensor(0xf000) == 0x7fff);
    perf_msr = 0;
    assert(ReadAsusSensor(0xf002) == 0x7fff);
    perf_msr = 0x920092006000920ULL; fsb_msr = 7;
    assert(ReadAsusSensor(0xf001) == 0x7fff);
    fsb_msr = 0x804;
    cpu_signature = 0xa0655;
    unsigned previous_msr_reads = msr_reads;
    assert(ReadAsusSensor(0xf000) == 0x7fff && msr_reads == previous_msr_reads);
    cpu_signature = 0x10676;
    ec[0x29] = 45; ec[0x2a] = 32;
    assert(ReadAsusSensor(0x1fb3) == 45);
    assert(ReadAsusSensor(0x9fb3) == 45);
    assert(ReadAsusSensor(0x9fb9) == 0x7fff);
    assert(ReadAsusSensor(0xa0cb) == 0x7fff);
    assert(ReadAsusSensor(0x1fb9) == 0); // Wrong electrical mode remains unavailable.
    ec[0x2a] = 96;
    assert(ReadAsusSensor(0x1fb9) == 0); // Observed G41MXE raw value.
    assert(ReadAsusSensor(0x1fb6) == 0); // CPU Package is not TMPIN2.
    ec[0x0c] = 3;
    ec[0x0e] = 0xa3; ec[0x19] = 2; // FAN2 count=675 -> 1000 RPM.
    ec[0x0d] = 0xe1; ec[0x18] = 0; // FAN1 count=225 -> 3000 RPM.
    assert(ReadAsusSensor(0x1fdf) == 1000);
    assert(ReadAsusSensor(0x9fdf) == 1000);
    assert(ReadAsusSensor(0x1fee) == 3000);
    assert(ReadAsusSensor(0x20cb) == 0); // Disabled ADC must not report stale data.
    ec[0x50] = 0xff;
    ec[0x20] = 70; ec[0x21] = 102; ec[0x22] = 186;
    ec[0x23] = 187; ec[0x24] = 210;
    assert(ReadAsusSensor(0x20cb) == 1120);
    assert(ReadAsusSensor(0xa0cb) == 1120);
    assert(ReadAsusSensor(0x20d3) == 1632);
    assert(ReadAsusSensor(0x20cd) == 11904);
    assert(ReadAsusSensor(0x20cf) == 5026);
    assert(ReadAsusSensor(0x20d1) == 3360);
    ec[0x20] = 0;
    assert(ReadAsusSensor(0xa0cb) == 0x7fff);
    ec[0x20] = 255;
    assert(ReadAsusSensor(0xa0cb) == 0x7fff);
    ec[0x20] = 70; ec[0x50] &= ~1U;
    assert(ReadAsusSensor(0xa0cb) == 0x7fff);
    assert(ReadAsusSensor(0x1ffc) == 0); // No third connected fan.
    ec[0x0e] = ec[0x19] = 0xff;
    assert(ReadAsusSensor(0x1fdf) == 0);
    assert(ReadAsusSensor(0x9fdf) == 0); // No pulses, not a proven absent header.
    ec[0x0e] = ec[0x19] = 0;
    assert(ReadAsusSensor(0x1fdf) == 0);
    assert(ReadAsusSensor(0x9fdf) == 0x7fff); // Invalid count, not 0 RPM.
    ec[0x0c] = 0;
    assert(ReadAsusSensor(0x1fee) == 0);
    assert(ReadAsusSensor(0x9fee) == 0x7fff); // Unsupported counter mode.
    ec[0x0c] = 3; ec[0x0e] = 0xa3; ec[0x19] = 2;
    high_reads = 0; unstable_high_reads = 6;
    assert(ReadAsusSensor(0x9fdf) == 0x7fff && high_reads == 6);
    high_reads = 0; unstable_high_reads = 6;
    assert(ReadAsusSensor(0x1fdf) == 0 && high_reads == 6);
    high_reads = 0; unstable_high_reads = 2;
    assert(ReadAsusSensor(0x9fdf) == 1000 && high_reads == 4);
    ec[0x29] = 0xff;
    assert(ReadAsusSensor(0x1fb3) == 0);
    ec[0x29] = 38; ec[0x51] = 0x10;
    assert(ReadAsusSensor(0x1fb3) == 0); // Disabled TMPIN1 must not report stale data.
    assert(ReadAsusSensor(0x9fb3) == 0x7fff);
    ec[0x51] = 8;
    assert(ReadAsusSensor(0x1fb3) == 38); // Enabled resistor mode.
    ec[0x51] = 0x11; ec[0x0c] = 7;
    ec[0x0e] = 0x53; ec[0x19] = 2;
    ec[0x0d] = ec[0x18] = 0xff;
    assert(ReadAsusSensor(0x1fdf) == 1134); // Real-board count 0x253.
    assert(ReadAsusSensor(0x1fee) == 0);
    ec[0x0e] = 0x50; ec[0x19] = 2;
    ec[0x29] = 38;
    assert(ReadAsusSensor(0x1fdf) == 1140); // 2026-09-29 snapshot: count 592.
    assert(ReadAsusSensor(0x1fb3) == 38);
    ec[0x29] = 0;
    assert(ReadAsusSensor(0x1fb3) == 0); // Enabled 0 C must remain a valid value.
    assert(ReadAsusSensor(0x9fb3) == 0); // Explicit-validity caller also preserves 0 C.
    ec[0x51] = 3; ec[0x2a] = 96;
    assert(ReadAsusSensor(0x9fb9) == 0x7fff); // Stale first conversion.
    ticks = 3579545ULL * 3 - 1;
    assert(ReadAsusSensor(0x9fb9) == 0x7fff);
    ticks++; ec[0x2a] = 31;
    assert(ReadAsusSensor(0x9fb9) == 31 && ReadAsusSensor(0x1fb9) == 31);
    ec[0x2a] = 0;
    assert(ReadAsusSensor(0x9fb9) == 0);
    ec[0x2a] = 128;
    assert(ReadAsusSensor(0x9fb9) == 0x7fff);
    ec[0x51] = 0x13;
    assert(ReadAsusSensor(0x9fb9) == 0x7fff && !mTempReady);
    ticks = 0xffff00;
    assert(ReadAsusSensor(0x9fb9) == 0x7fff);
    ec[0x51] = 3; ec[0x2a] = 32;
    ticks = (ticks + 3579545ULL * 3) & 0xffffff;
    assert(ReadAsusSensor(0x9fb9) == 32); // Counter wrap does not shorten settling.
    ec[0x55] = 0x80;
    assert(ReadAsusSensor(0x9fb9) == 0x7fff);
    ec[0x55] = 0; ec[0x51] = 0x83;
    assert(ReadAsusSensor(0x9fb9) == 0x7fff);
    config[0x30] = 0;
    assert(G41InstallSensors() == 0 && mEcBase == 0);
    config[0x30] = 1;
    assert(G41InstallSensors() == 0 && mEcBase == 0xa10);
    is_g41 = 0;
    unsigned previous_io_count = io_count;
    assert(G41InstallSensors() == 0 && mEcBase == 0 && io_count == previous_io_count);
    assert(raised == restored);
    puts("G41 sensor adapter: PASS (mocked I/O plus real-board register fixture)");
    return 0;
}
