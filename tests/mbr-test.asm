; Native CSM regression: real BIOS INT10, INT13 extensions and PIC timer.
bits 16
org 0x7c00
start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7c00
    sti
    mov [bootdrive], dl
    mov ax, 3
    int 0x10
    mov ax, 0x0f00
    int 0x10
    cmp al, 3
    jne fail
    mov si, video_ok
    call puts
    mov si, dap
    mov dl, [bootdrive]
    mov ah, 0x42
    int 0x13
    jc fail
    cmp dword [0x6000], 0x4d53434e ; "NCSM"
    jne fail
    mov si, disk_ok
    call puts
    mov ah, 0
    int 0x1a
    mov bp, dx
timer:
    mov ah, 0
    int 0x1a
    cmp dx, bp
    je timer
    mov si, timer_ok
    call puts
done:
    cli
    hlt
    jmp done
fail:
    mov si, failed
    call puts
    jmp done
puts:
    lodsb
    test al, al
    jz .ret
    push ax
    mov ah, 0x0e
    mov bx, 7
    int 0x10
    pop ax
    mov dx, 0x3f8
    out dx, al
    jmp puts
.ret:
    ret
bootdrive: db 0
align 4
dap: db 0x10, 0
     dw 1, 0x6000, 0
     dq 1
video_ok: db "NATIVE_CSM_INT10_PASS",13,10,0
disk_ok: db "NATIVE_CSM_INT13_LBA_PASS",13,10,0
timer_ok: db "NATIVE_CSM_PIC_TIMER_PASS",13,10,0
failed: db "NATIVE_CSM_MBR_FAIL",13,10,0
times 510-($-$$) db 0
dw 0xaa55
db "NCSM"
times (8*1024*1024)-($-$$) db 0
