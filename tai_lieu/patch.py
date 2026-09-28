import io, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ELDORADO_WEB")
BASE = "https://game.busidol.com"
LOCAL = "http://localhost:8023"

def rd(p):
    with io.open(p, "rb") as f:
        return f.read().decode("utf-8", "replace")

def wr(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)

# ---------- 1. loader.js: point get_app_file to local ----------
p = os.path.join(ROOT, "source_20240722", "loader.js")
s = rd(p)
before = s
s = s.replace(BASE + "/ELDORADO_WEB/get_app_file.php", LOCAL + "/ELDORADO_WEB/get_app_file.php")
wr(p, s)
print("loader.js patched:", before != s)

# ---------- 2. define_glo -> safe stub (drop antidevtools, keep platform) ----------
p = os.path.join(ROOT, "javascript_leveling", "define_glo_20241205.js")
wr(p, "var gTARGET_PLATFORM = 7;\nconsole.disableLogging = console.disableLogging || function(){};\n")
print("define_glo replaced with stub")

# ---------- 3. google_analytics -> local noop ----------
p = os.path.join(ROOT, "GoogleAnalytics", "google_analytics.js")
wr(p, "window.ga = window.ga || function(){};\nwindow.gtag = window.gtag || function(){};\n")
print("google_analytics -> noop")

# ---------- 4. pwsmart (paymentwall) stub ----------
p = os.path.join(ROOT, "pwsmart.1.3.js")
wr(p, "var PW = PW || {};\n")
print("pwsmart stub created")

# ---------- 5. eldorado_all: ENABLE_CRYPT=0 + host rewrite ----------
p = os.path.join(ROOT, "javascript_min", "eldorado_all_20260915.min.js")
s = rd(p)
before = s

s = s.replace("glo.APP_FEATURE.ENABLE_CRYPT=1", "glo.APP_FEATURE.ENABLE_CRYPT=0")

hosts = [
    "//game.busidol.com/", "//game.busidol.com",      # protocol-relative first
    "https://game.busidol.com", "http://game.busidol.com",
    "http://bueldorado.cafe24.com", "https://bueldorado.cafe24.com",
    "http://busidol2.cafe24.com", "https://busidol2.cafe24.com",
    "http://html5games.cafe24.com", "https://html5games.cafe24.com",
    "http://dungeonbreak.cafe24.com", "https://dungeonbreak.cafe24.com",
    "http://eldoradoskb.cafe24.com", "https://eldoradoskb.cafe24.com",
    "http://busiedu.cafe24.com", "https://busiedu.cafe24.com",
    "http://211.253.26.47:8089", "http://211.253.26.47:8080",
    "http://211.253.26.47:8081", "http://211.253.26.47:8090",
    "http://211.253.26.47:8092", "http://211.253.26.47:50074",
    "http://175.126.195.19", "http://14.63.197.40:8022",
]
for h in hosts:
    s = s.replace(h, LOCAL)

wr(p, s)
print("eldorado_all patched: bytes before=%d after=%d" % (len(before), len(s)))
print("remaining game.busidol.com refs:", s.count("game.busidol.com"))