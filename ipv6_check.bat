@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  IPv6 connectivity check  (pure ASCII on purpose: cmd mangles
rem  multi-byte chars when a bat file crosses its read boundary)
rem ============================================================

set "TARGET6=2400:3200::1"
set "HOP2=2409:xxxx:xxxx:xxxx::2"

echo ============================================================
echo  IPv6 Connectivity Check
echo ============================================================
echo.
echo [1] Local IPv6 addresses (look for 2409 / 240e / 2408 / 2400)
netsh interface ipv6 show address | findstr /i "2409 240e 2408 2400"
if errorlevel 1 echo     ^(no public IPv6 address found^)
echo.
echo [2] Default IPv6 route (should point at fe80::xx on Ethernet)
netsh interface ipv6 show route | findstr "::/0"
echo.
echo [3] Ping Alibaba DNS  %TARGET6%
echo     timeout  = maybe ICMP blocked by ISP (inconclusive)
echo     no route = upstream routing is broken (this is the bad one)
ping -6 -n 4 %TARGET6%
echo.
echo [4] Traceroute to %TARGET6%
echo     Hop 1 = your router, Hop 2 = ONT / CMCC edge.
echo     If hop 3 says "no route", the break is outside your house.
tracert -6 -d -h 6 -w 1500 %TARGET6%
echo.
echo [5] Compare with previous hop-2 address
echo     Was: %HOP2%
echo     If it answers, the ONT is alive but its upstream route is gone.
ping -6 -n 2 %HOP2%
echo.
echo [6] Public IPv6 (curl). Returns an address only if outbound works.
curl -6 -sS --noproxy "*" --max-time 10 https://ipv6.icanhazip.com
if errorlevel 1 echo     ^(curl failed or timed out - check curl.exe exists^)
echo.
echo [7] IPv4 baseline (should always return an address)
curl -4 -sS --noproxy "*" --max-time 10 https://ipv4.icanhazip.com
echo.
echo ============================================================
echo  Read [1] and [6] together:
echo    has 2409 addr + [6] returns  -> IPv6 fully working
echo    has 2409 addr + [6] times out -> stale address, upstream down
echo ============================================================
echo.
pause
