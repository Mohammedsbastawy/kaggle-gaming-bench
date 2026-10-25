import remote_exec

cmd = """su - gamer -c 'grep -E "(nvidia|GL)" /proc/31493/maps | head -n 30'"""
print(remote_exec.run_cmd(cmd))
