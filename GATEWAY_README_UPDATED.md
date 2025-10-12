# NEW GOTCHAS DISCOVERED - 2025-10-11

## Gotcha #11: TLS Certificate Conflict with ws:// URI

**Issue:** Basic Station fails with error:
```
connect() received a ssl argument for a ws:// URI, use a wss:// URI to enable TLS
```

**Cause:** Certificate files (`tc.crt`, `tc.key`) exist from previous configuration, but you're using `ws://` (non-TLS)

**Solution:** Remove certificate files before configuring non-TLS connection:

```bash
sudo systemctl stop basicstation
sudo rm -f /etc/station/tc.crt /etc/station/tc.key /etc/station/tc.trust
sudo klk_bs_config --enable --lns-uri "ws://yourserver:3001"
sudo systemctl start basicstation
```

**Prevention:** Always clean old configuration before switching between TLS/non-TLS

---

## Gotcha #12: DNS Resolution Failure (Use IP Address Instead)

**Issue:** Gateway can't resolve domain name even though DNS record exists

**Symptoms:**
```bash
nslookup yourserver.domain.com
# Returns: can't resolve 'yourserver.domain.com'

# But main domain works:
nslookup domain.com
# Returns: 151.80.58.99
```

**Cause:**
- DNS propagation delay (new subdomain not propagated to all DNS servers)
- Local DNS server doesn't have internet access
- DNS caching issues on gateway or local DNS server

**Solution:** Use IP address instead of domain name:

```bash
# Instead of:
sudo klk_bs_config --enable --lns-uri "ws://chirpstack.yourdomain.com:3001"

# Use:
sudo klk_bs_config --enable --lns-uri "ws://151.80.58.99:3001"
```

**Verification:** Test if DNS works from gateway before using domain name:

```bash
# Test main domain
nslookup yourdomain.com

# Test subdomain
nslookup chirpstack.yourdomain.com

# If subdomain fails but main domain works → DNS not propagated
# If both fail → local DNS issue, use IP address
```

**Note:** Using IP addresses for IoT gateways is a **recommended practice** in production to avoid DNS dependency.

---

## Troubleshooting DNS Issues

If you want to force the gateway to use public DNS:

```bash
# Configure systemd-resolved to use Google DNS
sudo mkdir -p /etc/systemd/resolved.conf.d/

echo "[Resolve]
DNS=8.8.8.8 1.1.1.1
FallbackDNS=8.8.4.4 1.0.0.1" | sudo tee /etc/systemd/resolved.conf.d/dns-servers.conf

# Restart DNS resolver
sudo systemctl restart systemd-resolved

# Flush DNS cache
sudo resolvectl flush-caches

# Test again
resolvectl query chirpstack.yourdomain.com
```

If DNS still doesn't work, check resolution status:

```bash
resolvectl status
```

---

**These gotchas were discovered during actual deployment on 2025-10-11**
