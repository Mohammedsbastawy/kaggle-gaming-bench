import asyncio
import json
import sys
import uuid
import ssl
import websockets

KERNEL_ID = 'a20a1457-cf3d-498e-9b3e-f60f9f14f8bf'
TOKEN_PATH = 'k/362292177/eyJhbGciOiJkaXIiLCJlbmMiOiJBMTI4Q0JDLUhTMjU2IiwidHlwIjoiSldUIn0..Q3faDMsHm0KG9HQdmChO4A.qYRhE0M3-wDV_I2vac0Pw-gYikp7T-p3ty0o3ncSJhtfmoW2sFtk51DbSma5Sl3PLxNKjjQhBOdlZrkpYsvjXTcUrEjAnEmwsASjPgzOU7Razfx3CuoNZGEQ2vvY7KqqwGzKeWd1JMfbhYIJffH8OUR8tCM6T8IPEffzICiAqQz_zZGCbZMOToAjU-KToZ3bRZjBq3tTUzuaa5XTdzLiYt6BLZ1FpZ4AbFWn40wIxb92w6oWVgyesAO2klyaIz7l.gJD1tm9ZDgRdlJjJskcFgw/proxy'
WS_URL = f'wss://kkb-production.jupyter-proxy.kaggle.net/{TOKEN_PATH}/api/kernels/{KERNEL_ID}/channels'

async def execute_code(code_str, timeout=60):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    output_lines = []
    try:
        async with websockets.connect(WS_URL, ssl=ctx) as ws:
            msg_id = uuid.uuid4().hex
            req = {
                'header': {'msg_id': msg_id, 'username': 'user', 'session': uuid.uuid4().hex, 'msg_type': 'execute_request', 'version': '5.2'},
                'parent_header': {},
                'metadata': {},
                'content': {'code': code_str, 'silent': False, 'store_history': True, 'user_expressions': {}, 'allow_stdin': False}
            }
            await ws.send(json.dumps(req))
            while True:
                resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                msg_type = resp.get('msg_type')
                if msg_type == 'stream':
                    text = resp['content']['text']
                    output_lines.append(text)
                    print(text, end='', flush=True)
                elif msg_type == 'execute_result' or msg_type == 'display_data':
                    text = resp['content'].get('data', {}).get('text/plain', '')
                    output_lines.append(text + '\n')
                    print(text, flush=True)
                elif msg_type == 'execute_reply':
                    break
                elif msg_type == 'error':
                    ename = resp['content'].get('ename')
                    evalue = resp['content'].get('evalue')
                    err_msg = f"ERROR: {ename}: {evalue}\n"
                    output_lines.append(err_msg)
                    print(err_msg, flush=True)
                    break
    except Exception as e:
        print(f"Exception during remote exec: {e}")
    return ''.join(output_lines)

def run_bash(cmd_str):
    py_code = f"import subprocess\nprint(subprocess.run({json.dumps(cmd_str)}, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout)"
    return asyncio.run(execute_code(py_code))

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_bash(' '.join(sys.argv[1:]))
    else:
        print("Usage: python exec_remote.py <bash_cmd>")
