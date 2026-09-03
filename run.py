import subprocess
import sys
import time
import threading

def run_script(script_name):
    while True:
        print(f"--> [Railway Bot Manager] Starting {script_name}...")
        process = subprocess.Popen(
            [sys.executable, "-u", script_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in process.stdout:
            print(f"[{script_name}] {line.strip()}")
        process.wait()
        print(f"--> [Railway Bot Manager] {script_name} stopped. Restarting...")
        time.sleep(5)

if __name__ == "__main__":
    print("--> [Railway Bot Manager] Starting both Telegram and Binance bots...")
    
    t1 = threading.Thread(target=run_script, args=("bot.py",))
    t2 = threading.Thread(target=run_script, args=("main.py",))
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
