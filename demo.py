from bnmmodule import bnm, iod, add, mul

# --- disk equality check ---
def eq_disk(x: iod, y: iod) -> bool:
    maxc = max(x.chunks, y.chunks)
    for i in range(maxc-1, -1, -1):
        if x._read_limb(i) != y._read_limb(i):
            return False
    return True

# --- SAFBROD setup ---
root = bnm("data_demo")  # base path

# --- config for ~500KB numbers ---
KB = 1024
LIMB_BYTES = 8
chunks_500KB = (500 * KB) // LIMB_BYTES  # ~64,000 limbs

# --- create disk numbers ---
a = iod("a", chunks_500KB)
b = iod("b", chunks_500KB)
c = iod("c", chunks_500KB)

# --- fill with small test pattern for demo ---
a._write_limb(0, 3)
b._write_limb(0, 4)
c._write_limb(0, 5)

# --- compute a^3 ---
a2 = mul(a, a)
a3 = mul(a2, a)

# --- compute b^3 ---
b2 = mul(b, b)
b3 = mul(b2, b)

# --- sum a^3 + b^3 ---
sum_ab3 = add(a3, b3)

# --- compute c^3 ---
c2 = mul(c, c)
c3 = mul(c2, c)

# --- check equality ---
if eq_disk(sum_ab3, c3):
    print("a^3 + b^3 == c^3 ???")
else:
    print("a^3 + b^3 != c^3 ✅ Fermat holds")

# --- optional cleanup ---
