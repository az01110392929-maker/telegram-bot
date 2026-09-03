import subprocess
import sys
import time
import threading

def run_script(script_name):
    while True:
        print(f"Starting {script_name}...")
        process = subprocess.Popen([sys.executable, script_name])
        process.wait()
        print(f"{script_name} stopped. Restarting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    print("Starting Telegram and Binance bots simultaneously...")
    
    # تشغيل بوت تيليجرام وبوت باينانس في وقت واحد
    t1 = threading.Thread(target=run_script, args=("bot.py",))
    t2 = threading.Thread(target=run_script, args=("main.py",))
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
