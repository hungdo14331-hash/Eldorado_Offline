import urllib.request, urllib.parse, http.cookiejar, json

base = "https://cocktail-terminal-subdivision-karl.trycloudflare.com"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def post(path, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(base + path, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    return op.open(req, timeout=30).read().decode()

# 1) login HUANDO
r = post("/ELDORADO_WEB/login_auth.php", {"acc": "HUANDO", "pw": "HUAN123"})
print("1 login:", r)
print("   cookies:", [(c.name) for c in cj])

# 2) doc balances (chi doc, khong doi gi) -- route theo cookie
b = post("/ELDORADO_WEB/toolshop/get_balances.php", {"FROM":"","TO":"","COUNT":""})
print("2 get_balances:", b)
