# NoCloud-QCOW2 镜像 · GitHub Actions 云端构建指南

> 适用：本机 libguestfs 1.48.6 + 内核 6.18 不兼容（`echo noop` 写 scheduler 失败），无法本机构建。
> 改用作者主路径：Fork 仓库 → GitHub Actions 云端构建（ubuntu-22.04 + root + 完整 KVM，无兼容问题）。
> 生成产物：`debian-13-nocloud-amd64.qcow2.xz`，解压后落到本仓库 `release/`。

## 为什么走云端

| 障碍 | 本机状态 |
|------|----------|
| 官方 `cloud.debian.org` 国内超时 | ✅ 已换南大镜像 `mirror.nju.edu.cn/debian-cdimage/cloud/trixie/20260501-2465/` |
| `/var/tmp` 权限 | ✅ 已 `chmod 1777 /var/tmp` |
| `/dev/kvm` 无权限 | ✅ 已用 `force_tcg` 绕过 |
| **appliance `echo noop` 写 scheduler 失败** | ❌ **死穴**：libguestfs 1.48.6 + 内核 6.18 不兼容，内核已移除 `noop`，apt 无更新可升 |

结论：本机 libguestfs 路线不可行，云端 CI（内核 5.15 + KVM）无此问题。

## 步骤

### 1. Fork 仓库
打开 https://github.com/iWangJiaxiang/NoCloud-QCOW2-image → 右上角 **Fork** → 选你的账号（gztxt1981）。

### 2. 改 fork 里的 `build.sh`（换南大镜像加速 CI 下载）
CI 在美国跑，官方源可达，但南大镜像更快且避免偶发超时。
用下方「fork 版 build.sh 全文」整体覆盖你 fork 的 `build.sh`（GitHub 网页编辑器直接粘贴即可）。

### 3. 开启并触发 Actions
- 进你 fork 的 **Actions** 页 → 首次需点 **I understand my workflows, go ahead and enable them**。
- 左侧 **Build Custom Debian QCOW2** → **Run workflow** → 分支选 `main` → **Run**。

### 4. 取产物
- 约 10–20 分钟跑完，自动在 **Releases** 生成 `debian-13-nocloud-amd64.qcow2.xz`。
- 下载后解压：
  ```bash
  xz -d debian-13-nocloud-amd64.qcow2.xz
  ```
- 放到本仓库：`技术文档/NoCloud-QCOW2-image/release/debian-13-nocloud-amd64.qcow2`

## fork 版 build.sh 全文（覆盖用）

```bash
#!/bin/bash
set -e

# CI 云端构建适配 (gztxt 2026-07-19):
# 官方 cloud.debian.org 国内直连超时，改用南京大学镜像固定版本 20260501-2465 加速下载。
# CI 环境用 direct 后端更稳（避免 libvirt 依赖）。
export LIBGUESTFS_BACKEND=direct

QCOW_URL="https://mirror.nju.edu.cn/debian-cdimage/cloud/trixie/20260501-2465/debian-13-nocloud-amd64-20260501-2465.qcow2"
QCOW_IMG="debian-13-nocloud-amd64.qcow2"
ROOT_PASSWORD="root"
OUTPUT_DIR="release"

echo "=> Downloading Debian 13 NoCloud QCOW2 image..."
if [ ! -f "${QCOW_IMG}" ]; then
  wget -q "${QCOW_URL}" -O "${QCOW_IMG}"
else
  echo "=> Image already exists, skipping download."
fi

# Ensure virt-customize exists
if ! command -v virt-customize &> /dev/null; then
  echo "=> virt-customize not found. Please install libguestfs-tools (and qemu-utils)."
  exit 1
fi

echo "=> Preparing release directory..."
mkdir -p "${OUTPUT_DIR}"
cp "${QCOW_IMG}" "${OUTPUT_DIR}/${QCOW_IMG}"

echo "=> Customizing Image..."

virt-customize -a "${OUTPUT_DIR}/${QCOW_IMG}" \
  --smp 2 \
  --timezone "Asia/Shanghai" \
  --root-password password:"${ROOT_PASSWORD}" \
  --run scripts/01-base-setup.sh \
  --run scripts/02-apt-packages.sh \
  --run scripts/03-docker.sh \
  --run scripts/04-dev-env.sh \
  --run scripts/05-opencode.sh \
  --run scripts/06-cleanup.sh

echo "=> Build completed successfully. Customized image is ready at: ${OUTPUT_DIR}/${QCOW_IMG}"
```

## 备注
- 本机已下载的 `debian-13-nocloud-amd64.qcow2`（391M）可保留作离线参考，但定制必须由 CI 完成。
- CI 自带 `xz -T0` 压缩（见 `.github/workflows/build.yml`），产物即 `.qcow2.xz`。
- 若 CI 下载南大镜像也慢，可改回官方 `https://cloud.debian.org/images/cloud/trixie/latest/debian-13-nocloud-amd64.qcow2`（CI 在美国可达）。
