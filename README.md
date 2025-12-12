# X Identity Shield — Consent Layer v0.6

**The cryptographic consent firewall that ends non-consensual deepfake nudity.**

- No blockchain
- No NFTs
- No bullshit
- 100% open source, MIT licensed
- Works today

### What it does
- You upload a selfie → get a permanent `fractal_id`
- You issue a signed consent capsule (a "soft NFT") that says exactly who can generate what kind of images of you
- At inference time, any platform calls `/check` → instantly allowed or denied + optional price
- You can revoke instantly, forever

Default: **no capsule = no generation of your likeness at all, even innocent art.**

### Quick start
```bash
git clone https://github.com/x-consent-layer/core.git
cd core
pip install -r requirements.txt
uvicorn consent_api:app --reload
```

→ Open http://127.0.0.1:8000/docs

### Endpoints
- `POST /fractal-id` → upload selfie → get your fractal ID
- `POST /capsule/issue` → create signed consent capsule
- `POST /check` → the actual gate X/Grok calls on every generation
- `POST /capsule/revoke/{id}` → instant kill switch

### Deploy
```bash
uvicorn consent_api:app --host 0.0.0.0 --port 80
```

Add Cloudflare + HTTPS → you now control global AI likeness consent.

### License
MIT — do whatever you want with it.

Made by people who are tired of deepfake porn.
# x-consent-layer
Nft fractal hash with monetization for end user. 
