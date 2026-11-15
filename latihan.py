import os

os.system("cls")

print("--- menggunakan list ---")
akun = ["akun1","akun2","akun3","akun4","akun5",]
login_gagal = [3,7,1,9,2]

total = 0
for lg in login_gagal :
    total += lg

print(f"total login gagal: {total} ")

print("---- menggunakan numpy ----")
import numpy as np


akun = np.array([3,7,1,9,2])

total = np.sum(login_gagal)

print(f"total login gagal : {total}" )