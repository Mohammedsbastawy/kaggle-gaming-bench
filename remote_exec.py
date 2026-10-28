import sys
import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = 'https://kkb-production.jupyter-proxy.kaggle.net/k/363261451/eyJhbGciOiJkaXIiLCJlbmMiOiJBMTI4Q0JDLUhTMjU2IiwidHlwIjoiSldUIn0..mnGqwK1h17uaOTFb6yCogQ.99Oxr6etd9jL_MJg2hJi2vf8P3UXRarCEMuD6AGdlYQN1OiH4_SpZ_5Ir2c_APAQZeOhaPnEBrNwzJ3V0GXJrPE_DJ8cNjyeK9QRf7srxkQgv9yVfb5DvGFCh38BH48M-6UgW-GoPBbZhLCnplea0ryZ6vgrbQZ-uIjTOPWbr5AAgQ9X2of5JzwZ9QqBc6jpA-S_eLdTYx3kHfWltXjUbQBKiUJ0FgeTGWYWHsC4ASRyDZil-fp8Hlx8GpZ2ur56.o3b17P80toBAh3IHx171Uw/proxy/proxy/9000/'

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
