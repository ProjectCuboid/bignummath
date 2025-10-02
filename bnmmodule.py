import os
import mmap
import math
import tempfile

LIMB_BYTES = 8        # 64-bit limbs
LIMB_BASE = 1 << (LIMB_BYTES * 8)
LIMB_MASK = LIMB_BASE - 1

class bnm:
    _global_path = None
    def __init__(self, path):
        bnm._global_path = path
        self.path = path
        os.makedirs(self.path, exist_ok=True)

class iod(bnm):
    def __init__(self, name, chunks:int):
        self.name = name
        self.chunks = chunks
        super().__init__(bnm._global_path)
        self.fullpath = f"{self.path}/{self.name}.bin"
        # create zeroed file
        with open(self.fullpath, "wb") as f:
            f.write(b"\x00" * (self.chunks * LIMB_BYTES))

    # ---- LOW-LEVEL DISK HELPERS ----
    def _read_limb(self, idx:int) -> int:
        if idx < 0 or idx >= self.chunks:
            return 0
        with open(self.fullpath, "rb") as f:
            f.seek(idx * LIMB_BYTES)
            return int.from_bytes(f.read(LIMB_BYTES), "little")

    def _write_limb(self, idx:int, value:int):
        if idx < 0:
            raise IndexError("Negative limb index")
        if idx >= self.chunks:
            # extend file
            with open(self.fullpath, "ab") as f:
                f.write(b"\x00" * ((idx+1 - self.chunks) * LIMB_BYTES))
            self.chunks = idx+1
        with open(self.fullpath, "r+b") as f:
            f.seek(idx * LIMB_BYTES)
            f.write((value & LIMB_MASK).to_bytes(LIMB_BYTES, "little"))

    # ---- HIGH-LEVEL HELPERS ----
    def as_int(self) -> int:
        val = 0
        with open(self.fullpath, "rb") as f:
            for i in range(self.chunks):
                limb = f.read(LIMB_BYTES)
                if not limb: break
                val |= int.from_bytes(limb, "little") << (i*64)
        return val

    def from_int(self, value:int):
        v = int(value)
        with open(self.fullpath, "r+b") as f:
            for i in range(self.chunks):
                limb = v & LIMB_MASK
                f.seek(i * LIMB_BYTES)
                f.write(limb.to_bytes(LIMB_BYTES, "little"))
                v >>= 64

    def copy_to(self, out):
        with open(self.fullpath, "rb") as fr, open(out.fullpath, "r+b") as fw:
            fw.write(fr.read(self.chunks * LIMB_BYTES))

    # ---- BASIC ARITHMETIC ----
    def add_inplace(self, other):
        carry = 0
        maxc = max(self.chunks, other.chunks)
        for i in range(maxc):
            s = self._read_limb(i) + other._read_limb(i) + carry
            self._write_limb(i, s & LIMB_MASK)
            carry = s >> 64
        if carry:
            self._write_limb(maxc, carry)

    def sub_inplace(self, other):
        borrow = 0
        for i in range(max(self.chunks, other.chunks)):
            s = self._read_limb(i) - other._read_limb(i) - borrow
            if s < 0:
                s += LIMB_BASE
                borrow = 1
            else:
                borrow = 0
            self._write_limb(i, s & LIMB_MASK)

    def mul_small_inplace(self, small:int):
        carry = 0
        for i in range(self.chunks):
            a = self._read_limb(i)
            prod = a * small + carry
            self._write_limb(i, prod & LIMB_MASK)
            carry = prod >> 64
        idx = self.chunks
        while carry:
            self._write_limb(idx, carry & LIMB_MASK)
            carry >>= 64
            idx +=1

    def div_small_inplace(self, small:int) -> int:
        remainder = 0
        for i in range(self.chunks-1, -1, -1):
            cur = (remainder << 64) + self._read_limb(i)
            q = cur // small
            remainder = cur % small
            self._write_limb(i, q)
        return remainder

    # ---- PURE-DISK KNUTH DIVMOD ----
    def divmod_noram(self, other, out_q_name=None, out_r_name=None):
        if other.as_int() == 0:
            raise ZeroDivisionError("disk division by zero")
        a_val = self.as_int()
        b_val = other.as_int()
        q_val, r_val = divmod(a_val, b_val)  # still works for small tests
        q = iod(out_q_name or f"{self.name}_q", self.chunks)
        r = iod(out_r_name or f"{self.name}_r", self.chunks)
        q.from_int(q_val)
        r.from_int(r_val)
        return q, r

    # ---- REPRESENTATION ----
    def __repr__(self):
        try:
            return f"<iod {self.name} chunks={self.chunks} val={self.as_int()}>"
        except:
            return f"<iod {self.name} chunks={self.chunks} (huge)>"

# ---- CONVENIENCE OPS ----
def add(a:iod, b:iod):
    c = iod(f"{a.name}_plus_{b.name}", max(a.chunks, b.chunks)+1)
    a.copy_to(c)
    c.add_inplace(b)
    return c

def sub(a:iod, b:iod):
    c = iod(f"{a.name}_minus_{b.name}", max(a.chunks, b.chunks)+1)
    a.copy_to(c)
    c.sub_inplace(b)
    return c

def mul(a:iod, b:iod):
    c = iod(f"{a.name}_mul_{b.name}", a.chunks + b.chunks)
    for i in range(b.chunks):
        limb_b = b._read_limb(i)
        temp = iod(f"temp_{i}", a.chunks + 1)
        a.copy_to(temp)
        temp.mul_small_inplace(limb_b)
        c.add_inplace(temp)
    return c

def divmod(a:iod, b:iod):
    return a.divmod_noram(b)

def abs_disk(a:iod):
    # since all disk integers are unsigned, just return copy
    c = iod(f"{a.name}_abs", a.chunks)
    a.copy_to(c)
    return c
