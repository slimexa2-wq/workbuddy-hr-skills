---
name: macos-app-install
description: 在 macOS 上安装并启动第三方 App（尤其是从 DMG 安装、未做 Apple 签名/公证的 App），处理「已损坏 / 无法打开 / 被系统拦截」等 Gatekeeper 问题，以及同名 App 双份注册导致「启动的是错的那一份」。当用户要求安装、打开、修复某个 .app 或 DMG，或提到「打不开」「已损坏」「被拦截」「xattr」「未签名」「启动错版本」「LaunchServices」「lsregister」时使用。
agent_created: true
---

# macOS 第三方 App 安装与启动

## 前提：先勘察，别猜

```bash
# 1. 挂载卷内容（DMG 通常含 .app + Applications 软链接 + 说明文件）
ls -la /Volumes/<卷名>/

# 2. 读安装说明（若有）
#    优先读卷内的 .txt / README，里面常写有针对该 App 的特定处理方式

# 3. 是否已安装？是否只是软链接？
ls -ld /Applications/<App>.app
readlink /Applications/<App>.app || echo "真实目录"
du -sh /Applications/<App>.app "/Volumes/<卷名>/<App>.app"   # 大小应一致
```

**关键陷阱**：如果 `/Applications/<App>.app` 是指向 DMG 的**符号链接**而非实体目录，
一旦推出 DMG（卷变 read-only / 卸载）App 立即失效。
必须确认为真实目录，大小与源一致才算安装完成。

### 用 `ditto` 复制，不要用 `cp -R`

```bash
ditto "/Volumes/<卷名>/<App>.app" "/Applications/<App>.app"
```

`ditto` 会保留代码签名、扩展属性和资源分叉；`cp -R` 可能破坏签名导致
`codesign` 报 `invalid signature`。

### 装之前先确认架构（沙盒内 `lipo` 常不可用）

```bash
file "/Volumes/<卷名>/<App>.app/Contents/MacOS/<可执行>"
# 期望: Mach-O universal binary with 2 architectures  或  Mach-O 64-bit executable arm64
```

`lipo -archs`、`strings` 在 WorkBuddy 沙盒中可能静默返回空，别把它们当唯一依据；
`file` 可靠。arch 不匹配（如 arm64-only 包想装到 Intel Mac）要提前报错，别装完才发现。

### 区分「成品 App」与「bootstrap 安装器」

同名 DMG 里那个 `.app` 不一定是成品，可能只是个几 MB 的引导安装器：

```bash
du -sh "/Volumes/<卷名>/<App>.app"                       # 成品通常 >100MB；<10MB 基本是安装器
/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "/Volumes/<卷名>/<App>.app/Contents/Info.plist"
ls "/Volumes/<卷名>/<App>.app/Contents/MacOS/"           # 可执行名是 <App>-Setup / <App>-Installer 即安装器
```

判定为安装器时：一样 `ditto` 到 `/Applications` 再 `open`，但它启动后**需要 GUI 交互**
（点 Install），且会自行下载源码/依赖，耗时以分钟计。此时要明确告知用户"窗口已打开，需点击"，
不要谎报"已安装完成"。查看进度用
`~/.<name>/logs/` 或 `~/Library/Logs/` 下的 bootstrap-installer.log / install.log。
若该工具同时提供脚本安装（如 `install.sh --non-interactive`），可优先用脚本路径，产物更可验证。

## 清除隔离属性（核心步骤）

Safari/浏览器下载的 App 会带 `com.apple.quarantine`，这是被拦截的根因。

```bash
# 量化确认（注意：无输出 ≠ 无问题，要显式计数）
xattr -r "/Applications/<App>.app" 2>/dev/null | grep -c "com.apple.quarantine"

# 清除（同时会清掉 com.apple.provenance）
xattr -cr "/Applications/<App>.app"

# 复查，应为 0
xattr -r "/Applications/<App>.app" 2>/dev/null | grep -c "com.apple.quarantine"
```

> `grep -c` 返回 0 匹配时退出码为 1，会让整条 `&&` 链看起来"失败"，属正常现象。

## 校验与启动

```bash
codesign -v --deep --verbose=2 "/Applications/<App>.app"   # 期望 valid on disk
open -a "/Applications/<App>.app"
```

关于 `spctl -a -vvv`：未公证 App 显示 `rejected` 是**预期现象**。
只要隔离属性已清除，Gatekeeper 就不会在启动时拦截，`rejected` 不影响使用。

## 验证真的跑起来了（沙盒内 ps 被禁）

`ps aux` 在沙盒中常返回 `operation not permitted`。改用：

```bash
pgrep -fl "<App名>"        # 拿到 PID + 可执行路径
lsappinfo list | grep -i "<App名>"   # 显示 LaunchServices 状态，(in front) 表示已到前台
```

`osascript -e 'tell application "System Events" ...'` 和 `screencapture` 需要额外授权，
沙盒内通常会失败，不要依赖它们做验证。

## 陷阱：同名 bundle ID 双份注册，LaunchServices 会选错路径

源码本地构建 / 打包产出的 App，经常同时存在于**构建目录**（如 `.../release/mac-arm64/<App>.app`）
和 `/Applications/<App>.app`。两者 `CFBundleIdentifier` 相同，LaunchServices 只认一个，
会出现「`open -a /Applications/<App>.app` 却拉起了构建目录那份」的诡异现象——
日后清理源码目录，应用就失效了。

**确认实际运行路径**：
```bash
pgrep -fl "<App>.app/Contents/MacOS/"          # 看真实可执行路径
lsappinfo list | grep -A2 -i 'bundleID="<你的 bundle id>"' | grep "bundle path"
```

**收敛到 /Applications 这份**：
```bash
LSR=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

# ① 必须先杀干净旧实例，否则同 bundle ID 已在运行，open 不会启新的
pkill -9 -f "<App>.app/Contents"
sleep 3; pgrep -f "<App>.app/Contents" && echo "仍有残留"

# ② 注销构建目录那份、注册 /Applications 那份
"$LSR" -u "/path/to/build/<App>.app"
"$LSR" -f "/Applications/<App>.app"

# ③ 再启动并复查 bundle path
open "/Applications/<App>.app"
lsappinfo list | grep -A2 -i 'bundleID="<你的 bundle id>"' | grep "bundle path"
```

另注意：先 `ditto` 安装好新版本再动旧的。若 `/Applications/<App>.app` 原本是**引导安装器**
（见上文判定方法），迁移到别处备份而不是直接删（如 `~/.<name>/<App>-bootstrap-installer-backup.app`），
便于回滚。

## 兜底方案

若 `xattr -cr` 后仍被拦截，再走系统设置路径：
系统设置 → 隐私与安全性 → 找到被拦截提示 → 「仍要打开」。

## 收尾

- 确认 App 进程已运行时，可询问用户是否推出安装卷（`hdiutil detach /Volumes/<卷名>`）。
  推出前先用 `hdiutil info \| grep -E "^image-path|^/dev/disk"` 定位原始 DMG 路径，
  确保用户日后仍能重新挂载。
- 不要把 DMG 里的 App **复制到 DMG 内的 Applications 软链接**上（read-only，会失败），
  必须落到真实的 `/Applications`。

## 两个实测踩坑

1. **挂载卷会在多次提权调用之间被自动卸载。**
   用 `hdiutil attach` 挂上、下一次提权 shell 里 `/Volumes/<卷名>` 可能已消失，
   `ditto` 报 `Cannot get the real path for source`。复制前先重新确认：
   ```bash
   ls /Volumes/ | grep -i "<卷名>" || hdiutil attach -nobrowse -quiet "<path.dmg>"
   ```
   因此**不要**在复制代码块里加 `set -e` —— 挂载失效会被误判成复制失败，后续步骤全被跳过。
2. **会话工作目录被删会让所有 shell 命令瘫痪。**
   工具会直接报 `Working directory does not exist or is not accessible`，
   连 `cd /tmp` 都救不了（命令根本没启动）。先探测：
   ```
   Glob(pattern="*", path=<workspace父目录>)
   ```
   目录真没了就用 Write 写一个占位文件把路径重建出来，通道即恢复。
