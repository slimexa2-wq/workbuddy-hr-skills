---
name: github-download-workaround
description: 当从 GitHub 下载大文件（源码 tarball、release 资产等）失败、卡住、速度极慢或被截断时使用。第 0 步先对本机 Mihomo 代理端口（主端口 7890 / 兼容端口 26801）与直连通道做量化测速，再结合 HTTP/1.1 分帧规避、Range 探测、预置浅克隆（--depth 1）或第三方镜像 + 官方 blob SHA 完整性校验完成下载。触发词：GitHub 下载慢、下载失败、Transferred a partial file、codeload、ghproxy、断点续传、源码包下不下来、HTTP2 framing layer、early EOF。
agent_created: true
---

# GitHub 大文件下载排查与加速绕行指南

## 第 0 步（必做）：先量化测速本机代理端口（`7890` / `26801`）与直连通道

本机现役代理为自建 **`mihomo`**（主端口 `127.0.0.1:7890`，兼容端口 `127.0.0.1:26801`，配置文件 `/Users/wangmini/.dsh/mihomo/config.v2.yaml`；原八戒 `26800` 已退役）。下载 GitHub 大文件前，**先用 5 秒实测对比 `7890` 代理与 `--noproxy '*'` 直连的真实吞吐**：

```bash
TESTURL="https://codeload.github.com/<owner>/<repo>/tar.gz/refs/tags/<tag>"
for mode in "-x http://127.0.0.1:7890" "-x http://127.0.0.1:26801" "--noproxy '*'"; do
  printf "%-28s " "$mode"
  eval curl -s $mode --max-time 6 -o /dev/null \
    -w '"code=%{http_code} speed=%{speed_download}B/s\n"' '"$TESTURL"'
done
# 选取 code=200 且 speed 最大的通道用于后续 git/curl 下载
```

**常见报错与环境变量规避**：
- `RPC failed; curl 16 Error in the HTTP2 framing layer`
- `curl 18 transfer closed with outstanding read data remaining` / `early EOF`

给 `git` 临时注入 `http.version=HTTP/1.1` 与大缓冲区（通过环境变量传递，**不污染用户全局 `.gitconfig`**）：

```bash
export GIT_CONFIG_COUNT=2 \
       GIT_CONFIG_KEY_0=http.version     GIT_CONFIG_VALUE_0=HTTP/1.1 \
       GIT_CONFIG_KEY_1=http.postBuffer  GIT_CONFIG_VALUE_1=524288000
```

---

## 核心认知：区分「带宽慢」与「单次会话时长截断」

```bash
# 对照测试：GitHub vs 其他 CDN
curl -s -x http://127.0.0.1:7890 --max-time 30 -o /dev/null \
  -w "GitHub  %{http_code} %{size_download}B %{speed_download}B/s\n" \
  "https://codeload.github.com/<owner>/<repo>/tar.gz/refs/tags/<tag>"
```

- **注意**：GitHub 官方 `codeload.github.com` 与 `api.github.com` 实测**不支持 HTTP Range 分块续传**（请求 `-r 0-1023` 仍返回 `200` 整包）。

---

## 通道优先级与实战技巧

| 优先级 | 通道 | 适用说明 |
|---|---|---|
| **1（首选）** | `git clone --depth 1 --branch <tag>` + `http://127.0.0.1:7890` | Git packfile 传输比裸 tarball 稳定得多；注意**不要**在抖动链路上加 `--filter=blob:none`（懒加载会产生海量小请求更容易断流）。 |
| **2** | 官方 `codeload` / Release 直下（走 `7890`） | 适合中小型源码包或 Release 二进制资产，下载后用 `gzip -t` 或 `shasum -a 256` 校验。 |
| **3** | 第三方镜像 + **官方 Git Tree Blob SHA 强校验** | 仅当主代理与直连均受阻时使用；拉下的源码**必须**经官方 API SHA 校验无误后才可执行。 |

### 常见镜像探测命令

```bash
for m in ghproxy.net gh-proxy.com ghfast.top gh.llkk.cc; do
  printf "%-16s " "$m"
  curl -s --noproxy '*' -r 0-1023 -o /dev/null --max-time 15 \
    -w "code=%{http_code} 收到=%{size_download} 均速=%{speed_download}B/s\n" \
    "https://$m/https://github.com/<owner>/<repo>/archive/refs/tags/<tag>.tar.gz"
done
```

### 安装器场景：预先放好浅克隆 checkout，跳过脚本内部劣质 clone

许多安装脚本内部会执行不带代理或带 `--filter=blob:none` 的 `git clone`。可先用 `http://127.0.0.1:7890` + `git clone --depth 1 --branch <tag>` 将仓库克隆到目标路径，再运行安装脚本以直接命中本地缓存。

---

## 走第三方镜像时的供应链完整性校验（必做）

```bash
# 1. 从官方 API 拉取该 tag 的完整文件树 SHA 清单
curl -s -x http://127.0.0.1:7890 --max-time 60 \
  "https://api.github.com/repos/<owner>/<repo>/git/trees/<tag>?recursive=1" -o tree.json
```

```python
# 2. 逐文件计算 git blob SHA-1 并与官方清单比对
import json, hashlib, os
tree = json.load(open('tree.json'))
assert not tree.get('truncated'), "清单被截断，请改用 git clone 校验"
base = '解压后的根目录'
bad = []
for x in tree['tree']:
    if x['type'] != 'blob': continue
    p = os.path.join(base, x['path'])
    if not os.path.exists(p):
        bad.append(('MISSING', x['path'])); continue
    data = open(p, 'rb').read()
    sha = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    if sha != x['sha']:
        bad.append(('MISMATCH', x['path']))
print('不一致文件数:', len(bad))
for b in bad[:20]: print(b)
```
只要 `bad` 非空即丢弃，严禁编译或执行被篡改的镜像包。
