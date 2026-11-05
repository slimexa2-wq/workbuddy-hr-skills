---
name: macos-proxy-vpn-check
description: 在 macOS 上排查代理 / VPN / Mihomo「开了但没生效」「部分网站打不开」的问题。基于本机现役自建 Mihomo 守护架构（主端口 7890 + 兼容端口 26801），用实测数据判定 TUN 是否接管、系统代理端口是否健康、出口 IP 真实归属、有无流量泄漏。当用户问「VPN 生效了吗」「代理没作用」「某些网站打不开」「出口 IP 不对」「Mihomo/Clash 没生效」时使用。
agent_created: true
---

# macOS 代理 / VPN（本机 Mihomo 架构）生效性排查

## 0. 本机当前代理基线架构（2026-11-01 权威现状，先知悉再排查）

- **现役核心引擎**：自建 **`mihomo`**（由 `launchd` 守护服务 `com.wangmini.mihomo` -> `/Users/wangmini/.dsh/mihomo/watch.sh` 托管，配置文件为明文 `/Users/wangmini/.dsh/mihomo/config.v2.yaml`）。
- **历史「八戒.app」已退役降级**：原 `/Applications/八戒.app`（FlClash 定制版）因内核频繁崩溃（曾产生 7.45GB core dump）与 `26800/26801` 端口漂移，**已退出代理接管，仅保留作为底层节点订阅供源**。
- **双监听端口设计**：
  1. **主混合监听端口：`127.0.0.1:7890`**（系统 HTTP / HTTPS / SOCKS 代理统一指向 `7890`）；
  2. **兼容监听端口：`127.0.0.1:26801`**（在 `config.v2.yaml` 的 `listeners` 中专门保留，用于兼容启动时冻结了旧环境变量 `HTTPS_PROXY=127.0.0.1:26801` 的长驻进程，如 Antigravity `language_server`，防止断连）。
- **核心分流策略**：`AI-GOOGLE` / `AI-GPT` 优先走日本低延迟节点（~68ms），异常时自动 fallback。

---

## 铁律：全部结论必须来自实测，禁止只看配置下结论

## 四线并行取证

```bash
# ① Mihomo 守护进程与监听进程是否在跑
pgrep -fl "mihomo|watch.sh|SkyCore|FlClash"
#   （沙盒内 ps aux 可能受限，优先用 pgrep 或 lsof）

# ② 系统代理设置是否指向 127.0.0.1:7890
scutil --proxy        # 检查 HTTPEnable/HTTPPort(7890)/HTTPSPort(7890)/SOCKSPort
networksetup -listallnetworkservices

# ③ TUN 是否接管（若开启 TUN 模式）
ifconfig | grep -E "^utun|^tun"

# ④ 7890 主端口与 26801 兼容端口是否真实在监听（决定性）
lsof -nP -iTCP:7890 -iTCP:26801 -sTCP:LISTEN
nc -z -G 2 127.0.0.1 7890 && echo "7890 通" || echo "7890 关闭"
nc -z -G 2 127.0.0.1 26801 && echo "26801 通" || echo "26801 关闭"
```

## 核心陷阱：路由表「缺 0/1」不是半覆盖

Clash / Mihomo 系 TUN 实现会拆成**八条细粒度路由**：

```
1        198.18.0.1   utunX      # 1.0.0.0/8
2/7      198.18.0.1   utunX      # 2.0.0.0 - 3.255.255.255
4/6      198.18.0.1   utunX
8/5      198.18.0.1   utunX
16/4     198.18.0.1   utunX
32/3     198.18.0.1   utunX
64/2     198.18.0.1   utunX
128.0/1  198.18.0.1   utunX
```

合计覆盖 `1.0.0.0 - 255.255.255.255`，**刻意跳过 `0.0.0.0/8`（保留段）**。看到没有 `0/1` 切勿误判为"只代理一半 IP"。

## 决定性验证：实测代理端口与真实出口 IP

```bash
# 1. 显式经 7890 主端口测试 Cloudflare trace（验证代理链路与出口国家代码）
curl -s -x http://127.0.0.1:7890 --max-time 8 https://1.1.1.1/cdn-cgi/trace | grep -E "^ip=|^loc=|^colo="
#   ip= 出口IP   loc=国家代码(如 JP/US/HK)   colo=接入点代码(NRT/HND=东京)

# 2. 验证 26801 兼容端口同样畅通
curl -s -x http://127.0.0.1:26801 --max-time 8 https://1.1.1.1/cdn-cgi/trace | grep -E "^ip=|^loc=|^colo="

# 3. 详细出口 ISP 与归属查询
curl -s -x http://127.0.0.1:7890 --max-time 10 "http://ip-api.com/json/?lang=zh-CN&fields=query,country,regionName,city,isp,org,timezone"
```

## 判定矩阵与自愈排障

| 现象 | 根因与处置方案 |
|---|---|
| `7890` 与 `26801` 均返回境外 `loc`（如 `JP`）且目标站点 HTTP 200 | ✅ 代理完全正常 |
| `7890` 连接被拒 | 检查 `launchctl list \| grep mihomo` 及 `/Users/wangmini/.dsh/mihomo/watch.sh`；可用 `launchctl kickstart -k gui/$(id -u)/com.wangmini.mihomo` 重启 |
| Google / OpenAI 正常，但某个特定站点超时或 403 | 属特定出口节点到目标站点的链路或 IP 信誉问题，检查 `/Users/wangmini/.dsh/mihomo/config.v2.yaml` 中对应 `proxy-groups` 与 `rules` 分流规则 |
| 测本地服务（如 `127.0.0.1:3425` Magpie 或 `:5179` Spider）报 `502` | 当前 Shell 环境变量注入了 `HTTP_PROXY`，访问本机回环地址时必须加 `--noproxy '*'`（或确保 `NO_PROXY="localhost,127.0.0.1"`） |

## 场景：单个站点打不开，但其他站点正常

```bash
# ① 看握手卡在哪一层（CONNECT 成功 ≠ 站点可达）
curl -sv -x http://127.0.0.1:7890 --max-time 12 -o /dev/null https://<目标域名>/ 2>&1 \
  | grep -E "CONNECT|Connection Established|TLS|handshake|timed out|HTTP/"

# ② 横向对比测试
for h in www.google.com chatgpt.com api.github.com <目标域名> ; do
  printf "%-24s " "$h"
  curl -s -x http://127.0.0.1:7890 -o /dev/null -w "HTTP %{http_code} %{time_total}s\n" --max-time 10 "https://$h/"
done
```

## 收尾要求
- 报结论时给出**实测证据表**（端口监听 / 出口 IP / 国家归属 / 目标站点 HTTP 状态码与耗时），不靠猜测下结论。
- 如需调整本机分流规则或节点组，修改 `/Users/wangmini/.dsh/mihomo/config.v2.yaml` 前**必须先备份**，修改后平滑重载并验证 `7890` 与 `26801` 双端口连通性。
