"""测试不同 DeepSeek 模型的响应速度"""
import urllib.request, json, time

KEY = open("F:/软件杯AI数字人/.env").read()
for line in KEY.split("\n"):
    if line.startswith("DEEPSEEK_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
        break

URL = "https://api.deepseek.com/chat/completions"

models = ["deepseek-chat", "deepseek-v4-flash"]
for model in models:
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "灵山大佛有多高？用3句话简短回答。"}],
            "max_tokens": 100,
            "temperature": 0.1,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(URL, data=data, headers={
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        }, method="POST")
        start = time.time()
        with urllib.request.urlopen(req, timeout=30) as resp:
            r = json.loads(resp.read().decode("utf-8"))
            elapsed = int((time.time() - start) * 1000)
            content = r["choices"][0]["message"]["content"]
            print(f"{model}: {elapsed}ms, {len(content)}chars")
    except Exception as e:
        print(f"{model}: ERROR - {e}")
