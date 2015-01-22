#!/usr/bin/python3

import sys

ax, cx, dx, bx, sp, bp, si, di = range(8)
regs=[0]*8

regs[sp] = 0x100

print("[2J")
def show_out():
    for i in range(25):
        for j in range(80):
            print("[%d;%dH%s"%(i+1,j+1,chr(mem[0x8000+j+80*i])))

def sign8(b):
    if b>127:
        return b-256
    return b

def sign16(b):
    if (b>>15)&1 != 0:
        return b-(1<<16)
    return b

def imm16():
    global pc
    x = mem[pc] + mem[pc+1]*256
    pc += 2
    return x
def imm8():
    global pc
    x = mem[pc]
    pc += 1
    return x

def get_reg_off(rm):
    if rm==0:
        return regs[bx] + regs[si]
    if rm==1:
        return regs[bx] + regs[di]
    if rm==2:
        return regs[bp] + regs[si]
    if rm==3:
        return regs[bp] + regs[di]
    if rm==4:
        return regs[si]
    if rm==5:
        return regs[di]
    if rm==6:
        return regs[bp]
    if rm==7:
        return regs[bx]

def get_rm(b, is8):
    mod = b>>6
    rm = b&7
    ans=0
    if mod==3:
        # register
        if is8:
            if rm<4:
                return (0,1,rm)
            else:
                return (0,2,rm&3)
        else:
            return (0,0,rm)
    else:
        if mod==0:
            if rm==6:
                disp = imm16()
                ans = disp
            else:   
                ans = get_reg_off(rm)
        elif mod==1:
            disp = imm8()
            ans = disp + get_reg_off(rm)
        elif mod==2:
            disp = imm16()
            ans = disp + get_reg_off(rm)
        if is8:
            return (1, 1, ans)
        else:
            return (1, 0, ans)
            
def get_r(b, is8):
    r = (b>>3)&7
    if is8:
        if r<4:
            return (0, 1, r)
        else:
            return (0, 2, r&3)
    return (0, 0, r)

def get_op(b):
    return (b>>3)&7

def get_r8(b):
    return get_r(b, True)
def get_r16(b):
    return get_r(b, False)
def get_rm8(b):
    return get_rm(b, True)
def get_rm16(b):
    return get_rm(b, False)

def push(x):
    mem[regs[sp]] = x&0xff
    mem[regs[sp]-1] = (x>>8)&0xff
    regs[sp] -= 2

def pop():
    regs[sp] += 2
    return mem[regs[sp]] + 256*mem[regs[sp]-1]

def ld(x):
    if type(x) == int:
        return x
    y = 0
    if x[0]==0:
        # register
        if x[1]==1:
            # low 8 bit
            y = regs[x[2]] & 0xff
        elif x[1] ==2:
            # high 8 bit
            y = (regs[x[2]]>>8)&0xff
        else:
            # 16 bits
            y = regs[x[2]]
    else:
        # memory
        if x[1] == 1:
            # 8 bits
            y = mem[x[2]]
        else:
            # 16 bits
            y = mem[x[2]] + mem[x[2]+1]*256
    return y

def st(x, y):
    if x[0]==0:
        # register
        if x[1]==1:
            # low 8 bit
            regs[x[2]] &= 0xff00
            regs[x[2]] += y & 0xff
        elif x[1] ==2:
            # high 8 bit
            regs[x[2]] &= 0xff
            regs[x[2]] += (y & 0xff)<<8
        else:
            # 16 bits
            regs[x[2]] = y&0xffff
    else:
        # memory
        if x[1] == 1:
            # 8 bits
            mem[x[2]] = y&0xff
        else:
            # 16 bits
            mem[x[2]] = y&0xff
            mem[x[2]+1] = (y>>8)&0xff

def op_mov(a,b):
    st(a, ld(b))

def op_cmp(a,b):
    x = ld(a)
    op_sub(a,b)
    st(a,x)

def set_flags(s, is8):
    if is8:
        flags[f_z] = (s&0xff)==0
        flags[f_s] = (s>>7)&1 == 1
        flags[f_c] = (s>>8) > 0
    else:
        # 16 bit
        flags[f_z] = (s&0xffff)==0
        flags[f_s] = (s>>15)&1 == 1
        flags[f_c] = (s>>16) > 0

def op_and(a,b):
    x = ld(a)
    y = ld(b)
    s = x&y
    st(a, s)
    set_flags(s, a[1]!=0)

def op_xor(a,b):
    x = ld(a)
    y = ld(b)

    s = x^y
    st(a, s)
    set_flags(s, a[1]!=0)

def op_or(a,b):
    x = ld(a)
    y = ld(b)
    s = x|y
    st(a, s)
    set_flags(s, a[1]!=0)

def op_sbb(a,b):
    y = ld(b)
    flags[f_c] = not flags[f_c]
    op_adc(a, ~y&0xffff)
    flags[f_c] = not flags[f_c]

def op_adc(a,b):
    x = ld(a)
    y = ld(b)
    c = 1 if flags[f_c] else 0
    s = x+y+c
    st(a, s)
    set_flags(s, a[1]!=0)

def op_sub(a,b):
    flags[f_c] = False
    op_sbb(a,b)

def op_add(a,b):
    flags[f_c] = False
    op_adc(a,b)

def op_xchg(a,b):
    x = ld(a)
    y = ld(b)

    st(a, y)
    st(b, x)


f_c, f_z, f_s = range(3)
flags=[0,0,0]
quiet=False
import sys
if sys.argv[1] == '-q':
    quiet = True
    sys.argv[1] = sys.argv[2]

with open(sys.argv[1], "rb") as f:
    if sys.version > '3':
        prog = list(f.read())
    else:
        prog = [ord(x) for x in f.read()]

pc=0
mem=prog + [0] * ((1<<16)-len(prog))

itera=0
while True:
    itera+=1
    op = imm8()
    #print '%3x %4x %s %x%x' % (pc-1, op, str(regs), mem[regs[sp]+1], mem[regs[sp]+2])
    if False:
        pass
    elif op == 0x01:
        # ADD r/m16, r16
        rm = imm8()
        o1 = get_rm16(rm)
        o2 = get_r16(rm)
        op_add(o1, o2)
    elif op == 0x04:
        imm = imm8()
        op_add((0,1,ax), imm)
    elif op == 0x09:
        b = imm8()
        r = get_r8(b)
        rm = get_rm8(b)
        op_or(rm, r)
    elif op==0x19:
        b = imm8()
        r = get_r8(b)
        rm = get_rm8(b)
        op_sbb(rm, r)
    elif op==0x20:
        b = imm8()
        r = get_r8(b)
        rm = get_rm8(b)
        op_and(rm, r)
    elif op==0x29:
        b = imm8()
        r = get_r16(b)
        rm = get_rm16(b)
        op_sub(rm, r)
    elif op==0x31:
        b = imm8()
        r = get_r16(b)
        rm = get_rm16(b)
        op_xor(rm, r)
    elif op==0x39:
        b = imm8()
        r = get_r16(b)
        rm = get_rm16(b)
        op_cmp(rm, r)
    elif op==0x3c:
        imm = imm8()
        op_cmp((0,1,ax), imm)
            
    elif 0x40 <= op < 0x48:
        # INC
        r = op-0x40
        op_add((0,0,r), 1)
    elif 0x48 <= op < 0x50:
        # DEC
        r = op-0x48
        op_add((0,0,r), -1)
    elif 0x50 <= op < 0x58:
        # PUSH
        r = op-0x50
        push(regs[r])
    elif 0x58 <= op < 0x60:
        # POP
        r = (0,0,op-0x58)
        x = pop()
        st(r, x)
    elif op==0x72:
        i = imm8()
        if flags[f_c]: pc += sign8(i)
    elif op==0x76:
        i = imm8()
        if flags[f_c] or flags[f_z]: pc += sign8(i)
    elif op==0x77:
        i = imm8()
        if not flags[f_c] and not flags[f_z]: pc += sign8(i)
    elif op==0x74:
        i = imm8()
        if flags[f_z]: pc += sign8(i)
    elif op==0x75:
        i = imm8()
        if not flags[f_z]: pc += sign8(i)
    elif op==0x79:
        i = imm8()
        if not flags[f_s]: pc += sign8(i)
    elif op==0x80:
        b = imm8()
        o = get_op(b)
        rm = get_rm8(b)
        imm = imm8()
        if o==0:
            op_add(rm, imm)
        elif o==1:
            op_or(rm, imm)
        else:
            raise Exception("Unimplemented: %x/%x " %(op,o))
    elif op==0x81:
        b = imm8()
        o = get_op(b)
        rm = get_rm16(b)
        imm = imm16()
        if o==7:
            op_cmp(rm, imm)
        else:
            raise Exception("Unimplemented: %x/%x " %(op,o))
    elif op==0x82:
        b = imm8()
        o = get_op(b)
        rm = get_rm16(b)
        imm = imm16()
        if o==0:
            op_add(rm, imm)
        else:
            raise Exception("Unimplemented: %x/%x " %(op,o))
    elif op==0x83:
        b = imm8()
        o = get_op(b)
        rm = get_rm16(b)
        imm = sign8(imm8())
        if o==0:
            op_add(rm, imm)
        elif o==2:
            op_adc(rm, imm)
        elif o==4:
            op_and(rm, imm)
        elif o==5:
            op_sub(rm, imm)
        elif o==7:
            op_cmp(rm, imm)
        else:
            raise Exception("Unimplemented: %x/%x " %(op,o))
    elif op==0x86:
        b = imm8()
        r = get_r8(b)
        rm = get_rm8(b)
        op_xchg(r, rm)
    elif op==0x88:
        b = imm8()
        r = get_r8(b)
        rm = get_rm8(b)
        op_mov(rm, r)
    elif op==0x89:
        b = imm8()
        r = get_r16(b)
        rm = get_rm16(b)
        op_mov(rm, r)
    elif op==0x8a:
        b = imm8()
        r = get_r8(b)
        rm = get_rm8(b)
        op_mov(r, rm)
    elif op==0x8b:
        b = imm8()
        r = get_r16(b)
        rm = get_rm16(b)
        op_mov(r, rm)
    elif 0x90 <= op < 0x98:
        r = op-0x90
        op_xchg((0,0,ax), (0,0,r))
    elif 0xb0 <= op < 0xb8:
        r = op-0xb0
        if r<4:
            r = (0,1,r)
        else:
            r = (0,2,r&3)
        i = imm8()
        op_mov(r, i)
    elif 0xb8 <= op < 0xc0:
        r = (0, 0, op-0xb8)
        i = imm16()
        op_mov(r, i)
    elif op==0xc7:
        b = imm8()
        o = get_op(b)
        rm = get_rm16(b)
        i = imm16()
        if o == 0:
            st(rm, i)
        
    elif op==0xe8:
        # CALL
        i = imm16()
        push(pc)
        pc += sign16(i)
    elif op==0xc3:
        pc = pop()
    elif op in (0x78, 0xf9):
        flags[f_c] = op == 0xf9
    elif op==0xeb:
        i = imm8()
        pc += sign8(i)
    elif op==0xf4:
        # HLT
        break
    elif op==0xfe:
        b = imm8()
        rm = get_rm8(b)
        o = get_op(b)
        if o==0:
            op_add(rm, 1)
        elif o==1:
            op_sub(rm, 1)
        else:
            raise Exception("Unimplemented: %2.2x/%x " %(op,o))
    elif op==0xff:
        b = imm8()
        o = get_op(b)
        rm = get_rm16(b)
        if o==2:
            pc += sign16(ld(rm))
        else:
            raise Exception("Unimplemented: %x/%x " %(op,o))
    else:
        raise Exception("Unimplemented: %2.2x" %op)
    if not quiet and itera%100==0:
        show_out()
        pass
    
