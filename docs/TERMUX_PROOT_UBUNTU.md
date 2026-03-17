# Termux + proot-distro Ubuntu

This is the recommended Android path when you want the full Linux runtime instead of native Termux packages.

## 1. Start from Termux

Install the Termux-side prerequisites:

```bash
pkg update
pkg install -y proot-distro git curl
```

Important:

- Use the F-Droid or GitHub build of Termux, not the Play Store build.
- This guide assumes you want to run ClawLite inside an Ubuntu rootfs managed by `proot-distro`.

## 2. Bootstrap Ubuntu and ClawLite

Run the wrapper installer from Termux:

```bash
curl -fsSL https://raw.githubusercontent.com/eobarretooo/ClawLite/main/scripts/install_termux_proot.sh | bash
```

What it does:

- installs `ubuntu` with `proot-distro` if needed
- installs `git`, `curl`, `python3`, `python3-venv`, and `build-essential` inside Ubuntu
- clones or updates `ClawLite` under `/root/ClawLite`
- runs `scripts/install.sh` inside Ubuntu

## 3. Enter Ubuntu and configure

```bash
proot-distro login ubuntu --shared-tmp
clawlite configure --flow quickstart
clawlite gateway
```

If `clawlite` is not on `PATH` in the first shell, reload the profile once:

```bash
source ~/.profile
```

## 4. Optional extras

Inside Ubuntu:

```bash
python3 -m pip install -e "/root/ClawLite[browser,telegram,media]"
python3 -m playwright install chromium
```

## Troubleshooting

- If `python3 -m venv` fails, install `python3-venv` inside Ubuntu and rerun the installer.
- If Playwright is not needed, skip the browser extra and the Chromium download.
- If you want to rerun the Ubuntu-side installer manually, use:

```bash
proot-distro login ubuntu --shared-tmp -- /bin/bash -lc 'cd /root/ClawLite && bash scripts/install.sh'
```
