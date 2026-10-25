import sys
sys.path.append(r'd:\Kaggle Cloud Gaming')
import remote_exec

if __name__ == '__main__':
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    cmd = ' '.join(sys.argv[1:])
    print(remote_exec.run_cmd(cmd))
