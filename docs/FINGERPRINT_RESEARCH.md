# Device fingerprinting — researched background (condensed from `sporty.md`)

Why automated registration flows on consumer platforms (Gmail, SportyBet, …)
are a design problem rather than a coding problem. Keep this frame of mind when
building the SportyBet adapter: **a real browser that looks and behaves exactly
like a human's beats every script that claims to be one.**

## What platforms fingerprint

A signup page does not just render a form. It builds a **multi-layered
fingerprint** of your device, browser, network, and behavior, then fuses it
into a risk score:

### 1. JavaScript-level (browser API)
- User-Agent, `navigator.platform`, `language(s)`, `hardwareConcurrency`,
  `deviceMemory`, screen size/area/pixel-ratio, timezone, system time.
- `navigator.webdriver` — set to `true` by default in Selenium/WebDriver; a
  near-instant ban signal.
- **Canvas** fingerprint — hidden drawing hashed: depends on OS font rendering,
  GPU driver, and the browser's shaping engine.
- **WebGL** renderer string + extensions (e.g. `SwiftShader` on headless, real
  `ANGLE (NVIDIA, …)` on a desktop GPU).
- Installed plugins, system **fonts**, and audio-context hashing.

### 2. Network-level (visible before JS even runs)
- **JA3/JA4 TLS fingerprints** — cipher-suite order, TLS extension order,
  supported groups. Distinct per real browser vs HTTP libraries.
- **p0f-style TCP fingerprinting** — TTL, window size, MSS, TCP option
  order (SACK/timestamps), DF flag. The server classifies your OS from the SYN.
- A browser that *claims* Windows but *TCPs* like a Linux server (or a known
  proxy tool) is an instant mismatch flag.

### 3. Behaviour + history
- Mouse velocity/curvature/jitter, scroll timing, keystroke dynamics.
- Existing cookies/accounts and the device's reputation history.
- Volume: many accounts from one IP/device in a short window.

## Why naive automation loses on every layer

| Tool | Fingerprint leak |
|---|---|
| Selenium / WebDriver | `navigator.webdriver=true`, WebDriver headers, often headless, odd screen sizes |
| Playwright / Puppeteer default | headless-ish defaults; canvas/WebGL can differ from real devices |
| Antidetect browsers | impossible combos (Windows UA + Linux fonts + virtual GPU), TCP/IP still mismatches |
| VPS / datacenter IPs | low IP reputation; VMs expose generic GPUs, thin fonts, odd cores/RAM |
| Scripted input | perfect fill timing, linear cursor paths — no micro-jitter |

The models are trained on billions of events; they know what normal
Windows/Chrome, macOS/Safari, Android/Chrome look like *in every layer at once*.

## Net effect on a real SportyBet integration

Even *exactly correct* form-filling loses unless the environment is coherent:

1. Real, persistent browser profile (headed) — un-tampered JS fingerprint.
2. Network egress that matches the claimed device class (browser TCP/TLS, sane
   IP reputation).
3. Human input pacing: natural keystrokes, inter-field delays, dwell times.
4. Low creation rate per IP/device — **one registration at a time**.
5. Accept that OTP delivery over real SMS is not instant: 20–60s is normal.

`app/providers/sportybet.py` implements points 1, 3, 4, and 5; points 2 is
operator-infrastructure (egress/reputation). This is exactly the "losing
battle" framing from the original research: you cannot win on a single signal,
but a coherent, authorized, rate-limited, real-browser flow is the only
plausible path — and it still requires the operator's authorization on a live
platform like sportybet.com.