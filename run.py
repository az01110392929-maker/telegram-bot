import subprocess
import sys
import time

def run_script(script_name):
    return subprocess.Popen([sys.executable, script_name])

if __name__ == "__main__":
    print("بدء تشغيل منظومة البوتات المتكاملة...")

    # تشغيل بوت التلجرام وبوت باينانس معاً
    p1 = run_script("bot.py")
    p2 = run_script("binance_bot.py")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        p1.terminate()
        p2.terminate()
        print("تم إيقاف النظام الموحد.")
      
