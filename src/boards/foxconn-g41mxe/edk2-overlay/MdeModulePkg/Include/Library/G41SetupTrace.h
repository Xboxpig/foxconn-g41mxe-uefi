/** @file
  Screen and log checkpoints for the G41MXE Setup latency investigation.

  SPDX-License-Identifier: BSD-2-Clause-Patent
**/

#ifndef G41_SETUP_TRACE_H_
#define G41_SETUP_TRACE_H_

#ifdef G41MXE_SETUP_TRACE
#include <Guid/GlobalVariable.h>
#include <Library/BaseLib.h>
#include <Library/DebugLib.h>
#include <Library/TimerLib.h>
#include <Library/UefiLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>

STATIC UINT64  mG41TraceStartTsc;
STATIC UINT64  mG41TraceTicksPerMs;

STATIC
VOID
G41SetupTrace (
  IN CONST CHAR16  *Stage
  )
{
  CONST EFI_GUID  GlobalGuid = EFI_GLOBAL_VARIABLE;
  UINT64          CounterStart;
  UINT64          CounterEnd;
  UINT64          CounterFirst;
  UINT64          CounterLast;
  UINT64          CounterTicks;
  UINT64          CounterFrequency;
  UINT64          Tsc;
  UINT64          ElapsedMs;
  UINTN           DataSize;
  UINT16          Timeout;
  EFI_STATUS      VariableStatus;

  if (mG41TraceTicksPerMs == 0) {
    // The ACPI counter wraps every 4.7 seconds. Use it only for this short
    // calibration; the 64-bit TSC then covers the entire long Setup delay.
    CounterFrequency = GetPerformanceCounterProperties (&CounterStart, &CounterEnd);
    CounterFirst     = GetPerformanceCounter ();
    mG41TraceStartTsc = AsmReadTsc ();
    MicroSecondDelay (10000);
    Tsc         = AsmReadTsc ();
    CounterLast = GetPerformanceCounter ();
    CounterTicks = (CounterLast >= CounterFirst) ?
                     CounterLast - CounterFirst :
                     CounterEnd - CounterFirst + CounterLast - CounterStart + 1;
    if ((CounterTicks != 0) && (CounterFrequency != 0)) {
      mG41TraceTicksPerMs = DivU64x64Remainder (
                             MultU64x64 (Tsc - mG41TraceStartTsc, CounterFrequency),
                             MultU64x64 (CounterTicks, 1000),
                             NULL
                             );
    }
  }

  Tsc       = AsmReadTsc ();
  ElapsedMs = (mG41TraceTicksPerMs != 0) ?
                DivU64x64Remainder (Tsc - mG41TraceStartTsc, mG41TraceTicksPerMs, NULL) : 0;
  DataSize       = sizeof (Timeout);
  VariableStatus = gRT->GetVariable (L"Timeout", (EFI_GUID *)&GlobalGuid, NULL, &DataSize, &Timeout);
  DEBUG ((DEBUG_ERROR, "G41MXE trace: %Lu ms TSC=%Lu variable=%r: %s\n", ElapsedMs, Tsc, VariableStatus, Stage));

  if ((gST->ConOut != NULL) && (gST->ConsoleOutHandle != NULL)) {
    // Repaint only three text lines. A full framebuffer clear at every
    // checkpoint would add graphics work to the latency being measured.
    gST->ConOut->SetAttribute (gST->ConOut, EFI_LIGHTGRAY | EFI_BACKGROUND_BLACK);
    gST->ConOut->SetCursorPosition (gST->ConOut, 0, 0);
    Print (L"G41MXE Setup Trace  %Lu ms (scope)                          \n", ElapsedMs);
    Print (L"%-64s\n", Stage);
    Print (L"Variable service: %-32r\n", VariableStatus);
  }
}
#else
#define G41SetupTrace(Stage)  do { } while (FALSE)
#endif

#endif
