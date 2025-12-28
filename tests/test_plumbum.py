from plumbum import local, FG, BG, RETCODE, TEE
from plumbum.cmd import sudo

# FG:  前台执行，实时显示输出
retcode = sudo["apt", "update"] & FG
if retcode == 0:
    print("执行成功")

# BG: 后台执行
# future = sudo["apt", "update"] & BG
# # ...  做其他事情
# retcode, stdout, stderr = future.wait()

# RETCODE: 只返回退出码
retcode = sudo["apt", "update"] & RETCODE

# TEE: 同时显示和捕获输出
stdout = sudo["apt", "update"] & TEE

print(stdout)

retcode, stdout, stderr = sudo["apt", "update"].run(retcode=None)

if retcode == 0:
    print("✓ apt update 成功")
else:
    print(f"✗ apt update 失败 (exit code: {retcode})")
    print(f"错误信息: {stderr}")



# TEE 会同时显示在终端并返回输出
output = (sudo["apt", "update"] & TEE)

# 或者使用 TEE(retcode=...)
output = (sudo["apt", "update"] & TEE(retcode=None))




cmd = sudo["apt", "update"]
proc = cmd. popen()

# 实时读取输出
while True: 
    line = proc.stdout.readline()
    if not line:
        break
    print(f">>> {line.strip()}")








print()