import sys
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = 'https://kkb-production.jupyter-proxy.kaggle.net/k/362246212/eyJhbGciOiJkaXIiLCJlbmMiOiJBMTI4Q0JDLUhTMjU2IiwidHlwIjoiSldUIn0..HYzAD-ew6IqX5LjGxgSeUA.Q7I_CX8xdpo49V74I5a7qITKVb6KfVMfSHrRkC0gUy5aZkkDnqcVPriCz0sf5w4eU7Av_yh7d6diz5TOOWemlWgiCpCaSWh5dJVyx1ztD_8PfWRfwpGCl_dNnQTfGQJvKlyNusElsmskaUI0KVj0OcBNXBAHuzaZtSyX-djx6oXkw_P3L9YOEF-bGLrKGRt0h-XsPNxp8gslhVH65N2180Qo5T-i9Fm7DMvikijQyW8IkK3JRsHydBjSZtVF1N0C.QGuc8yGeWv1jyrSfS4IUTQ/proxy/proxy/9000/'

def run_cmd(cmd, timeout=120):
    req = urllib.request.Request(BASE, data=cmd.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'}, method='POST')
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.read().decode('utf-8')
    except Exception as e:
        return f"REMOTE_EXEC_ERROR: {e}"

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = ' '.join(sys.argv[1:])
        print(run_cmd(cmd))
    else:
        print("Usage: python remote_exec.py <command>")
