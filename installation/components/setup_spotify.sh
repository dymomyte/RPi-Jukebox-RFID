#!/usr/bin/env bash

# Setup script for the optional Spotify playback backend.
#
# This installs and configures `go-librespot` (https://github.com/devgianlu/go-librespot)
# as a Spotify Connect / playback engine that the Jukebox controls through its local
# REST API. It is a *standalone* component script, run directly by the user after the
# main installation - much like `setup_hifiberry.sh`:
#
#   cd ~/RPi-Jukebox-RFID/installation/components
#   ./setup_spotify.sh
#
# What it does (idempotent - safe to re-run):
#   1. Detects the Pi architecture and downloads a pinned go-librespot release binary.
#   2. Installs the binary to ~/.local/bin/go-librespot.
#   3. Writes a go-librespot config.yml (PulseAudio backend, REST API on port 3678,
#      credential persistence) into ~/.config/go-librespot/.
#   4. Installs and enables a systemd *user* service `go-librespot.service`
#      (consistent with how the Jukebox runs MPD and the core daemon as user services,
#      so go-librespot shares the user's PulseAudio session and the same sink the
#      jukebox uses).
#   5. Guides the user through the one-time Spotify device authentication.
#
# NOTE: A Spotify *Premium* account is required. go-librespot only supports
# OAuth / Zeroconf login - username/password auth no longer exists.
#
# For the full user guide see documentation/builders/components/spotify.md

# Source shared helpers (get_architecture, download_from_url, is_service_enabled, ...)
# We deliberately reuse the installer helpers instead of duplicating arch detection.
source ../includes/02_helpers.sh

# -----------------------------------------------------------------------------
# Pinned versions / locations  (bump GO_LIBRESPOT_VERSION here to update)
# -----------------------------------------------------------------------------
# go-librespot release to install. Verified asset naming against
# https://github.com/devgianlu/go-librespot/releases/tag/v0.7.4
GO_LIBRESPOT_VERSION="v0.7.4"
GO_LIBRESPOT_REPO="https://github.com/devgianlu/go-librespot"

# go-librespot REST API: host and port the Jukebox `spotify` component talks to.
# Keep in sync with the `spotify:` block in jukebox.yaml (host/port).
GO_LIBRESPOT_API_HOST="localhost"
GO_LIBRESPOT_API_PORT="3678"

# Spotify Connect device name shown in the Spotify apps during Zeroconf login.
GO_LIBRESPOT_DEVICE_NAME="Phoniebox"

# Install locations (all in the current user's home - go-librespot runs as a user service).
INSTALL_BIN_DIR="${HOME}/.local/bin"
INSTALL_BIN_PATH="${INSTALL_BIN_DIR}/go-librespot"
CONFIG_DIR="${HOME}/.config/go-librespot"
CONFIG_PATH="${CONFIG_DIR}/config.yml"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="go-librespot.service"
SERVICE_PATH="${SYSTEMD_USER_DIR}/${SERVICE_NAME}"

script_name=$(basename "$0")

# -----------------------------------------------------------------------------
# Lightweight logging (this script runs standalone, outside the installer's
# logging framework, so we use plain echo like setup_hifiberry.sh does).
# -----------------------------------------------------------------------------
log_info() { echo "[setup_spotify] $1"; }
log_err() { echo "[setup_spotify] ERROR: $1" >&2; }
die() { log_err "$1"; exit 1; }

# -----------------------------------------------------------------------------
# Map the project architecture name to a go-librespot release asset.
# Asset names (verified for v0.7.4):
#   go-librespot_linux_arm64.tar.gz       64-bit Pi OS (aarch64)
#   go-librespot_linux_armv6.tar.gz       generic 32-bit ARM (also used for armv7)
#   go-librespot_linux_armv6_rpi.tar.gz   Raspberry Pi specific armv6 build
#   go-librespot_linux_x86_64.tar.gz      desktop / 64-bit dev machines
# There is no dedicated armv7 asset; the armv6 build runs on armv7 hardware.
# -----------------------------------------------------------------------------
get_asset_name() {
    local arch
    arch=$(get_architecture)
    case "${arch}" in
        arm64)
            echo "go-librespot_linux_arm64.tar.gz" ;;
        armv7)
            # 32-bit Pi OS on Pi 2/3 (armv7l). No armv7 asset -> use armv6 (compatible).
            echo "go-librespot_linux_armv6.tar.gz" ;;
        armv6)
            # Pi Zero / Pi 1. Use the Raspberry-Pi-specific build.
            echo "go-librespot_linux_armv6_rpi.tar.gz" ;;
        x86_64 | amd64)
            echo "go-librespot_linux_x86_64.tar.gz" ;;
        *)
            die "Unsupported architecture '${arch}'. No go-librespot binary available." ;;
    esac
}

# -----------------------------------------------------------------------------
# Download and install the pinned go-librespot binary (idempotent: skips if the
# requested version is already installed).
# -----------------------------------------------------------------------------
install_binary() {
    local asset download_url tmp_dir

    if [ -x "${INSTALL_BIN_PATH}" ]; then
        local installed_version
        # `go-librespot --version` prints something like "go-librespot v0.7.4 ..."
        installed_version=$("${INSTALL_BIN_PATH}" --version 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -n1)
        if [ "${installed_version}" = "${GO_LIBRESPOT_VERSION}" ]; then
            log_info "go-librespot ${GO_LIBRESPOT_VERSION} already installed - skipping download."
            return 0
        fi
        log_info "Replacing go-librespot ${installed_version:-unknown} with ${GO_LIBRESPOT_VERSION}."
    fi

    asset=$(get_asset_name)
    download_url="${GO_LIBRESPOT_REPO}/releases/download/${GO_LIBRESPOT_VERSION}/${asset}"
    tmp_dir=$(mktemp -d)

    log_info "Downloading ${asset} (${GO_LIBRESPOT_VERSION}) for $(get_architecture) ..."
    download_from_url "${download_url}" "${tmp_dir}/${asset}"

    log_info "Extracting and installing to ${INSTALL_BIN_PATH} ..."
    tar -xzf "${tmp_dir}/${asset}" -C "${tmp_dir}" || die "Failed to extract ${asset}"

    # The binary inside the tarball is named `go-librespot`.
    local extracted_bin="${tmp_dir}/go-librespot"
    [ -f "${extracted_bin}" ] || die "Expected 'go-librespot' binary not found in archive."

    mkdir -p "${INSTALL_BIN_DIR}"
    install -m 755 "${extracted_bin}" "${INSTALL_BIN_PATH}"
    rm -rf "${tmp_dir}"

    log_info "Installed go-librespot ${GO_LIBRESPOT_VERSION}."
}

# -----------------------------------------------------------------------------
# Write the go-librespot config.yml.
#
# Config keys verified against go-librespot's config_schema.json / README:
#   - audio_backend: pulseaudio  -> routes audio into the user's PulseAudio
#       session. This is the SAME PulseAudio server (and therefore the same
#       default sink) the Jukebox configures via run_configure_audio.py, so
#       Spotify plays out of the same speakers as the local MPD library and
#       respects the jukebox volume control. We intentionally do NOT pin
#       `audio_device` so go-librespot follows PulseAudio's default sink.
#   - server.enabled/address/port -> the local REST API the Jukebox drives.
#   - credentials.type: zeroconf -> headless-friendly login: pick the box from
#       the Spotify app's device list (Spotify Connect). persist_credentials
#       stores the login so it survives reboots. Switch to `interactive` for
#       OAuth (see the auth section / docs).
#
# Idempotent: only writes the file if it does not already exist, so a user's
# manually tweaked config and (more importantly) their stored credentials are
# never clobbered on re-run.
# -----------------------------------------------------------------------------
write_config() {
    mkdir -p "${CONFIG_DIR}"

    if [ -f "${CONFIG_PATH}" ]; then
        log_info "Config already exists at ${CONFIG_PATH} - leaving it untouched."
        return 0
    fi

    log_info "Writing go-librespot config to ${CONFIG_PATH} ..."
    cat > "${CONFIG_PATH}" <<EOF
# go-librespot configuration for RPi-Jukebox-RFID
# Generated by installation/components/setup_spotify.sh
# Reference: https://github.com/devgianlu/go-librespot

# Spotify Connect device name (shown in the Spotify app device list).
device_name: ${GO_LIBRESPOT_DEVICE_NAME}
device_type: speaker

# Route audio through PulseAudio so Spotify shares the same sink/volume as the
# rest of the Jukebox (configured by run_configure_audio.py). Leave audio_device
# unset to follow PulseAudio's default sink.
audio_backend: pulseaudio

# Local REST API the Jukebox 'spotify' component controls.
server:
  enabled: true
  address: ${GO_LIBRESPOT_API_HOST}
  port: ${GO_LIBRESPOT_API_PORT}

# Login method. 'zeroconf' lets you log in from the Spotify app (Spotify Connect)
# without typing credentials on the Pi - ideal for a headless box. Credentials are
# persisted so the box reconnects automatically after a reboot.
# For headless OAuth instead, set type to 'interactive' (see the docs).
credentials:
  type: zeroconf
  zeroconf:
    persist_credentials: true
EOF
    chmod 600 "${CONFIG_PATH}"
    log_info "Config written. Credentials will be stored under ${CONFIG_DIR}."
}

# -----------------------------------------------------------------------------
# Install and enable the systemd *user* service.
# A user service (rather than a system service) is used on purpose: that is how
# the Jukebox runs MPD and the core daemon, and it ensures go-librespot runs
# inside the user's PulseAudio session.
# Idempotent: overwriting the unit file and re-enabling is harmless.
# -----------------------------------------------------------------------------
install_service() {
    log_info "Installing systemd user service ${SERVICE_NAME} ..."
    mkdir -p "${SYSTEMD_USER_DIR}"

    cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=go-librespot Spotify backend for RPi-Jukebox-RFID
# PulseAudio provides the audio sink we route Spotify into.
After=network-online.target pulseaudio.service sound.target
Wants=network-online.target

[Service]
ExecStart=${INSTALL_BIN_PATH} --config_dir ${CONFIG_DIR}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
    chmod 644 "${SERVICE_PATH}"

    systemctl --user daemon-reload
    systemctl --user enable "${SERVICE_NAME}"
    # (Re)start so the API is up for the auth step below.
    systemctl --user restart "${SERVICE_NAME}"

    # Make sure the user services keep running when the user is not logged in
    # (otherwise systemd kills them at logout, which would stop Spotify on a
    # headless box). MPD relies on the same mechanism.
    sudo loginctl enable-linger "$(whoami)" 2>/dev/null || \
        log_info "Could not enable linger automatically - run 'sudo loginctl enable-linger \$USER' if Spotify stops when you log out."

    log_info "Service ${SERVICE_NAME} enabled and started."
}

# -----------------------------------------------------------------------------
# One-time authentication guidance.
# With the default 'zeroconf' credentials type the user logs in from the Spotify
# app, so there is nothing to type on the Pi. We just tell them how.
# (For 'interactive'/OAuth the daemon logs an auth URL; complete it on a headless
# box with `curl http://127.0.0.1:<callback_port>/login?code=...` - see the docs.)
# -----------------------------------------------------------------------------
print_auth_instructions() {
    cat <<EOF

------------------------------------------------------------------------
 One-time Spotify authentication
------------------------------------------------------------------------
go-librespot is running and advertised on your network as a Spotify
Connect device named:

    ${GO_LIBRESPOT_DEVICE_NAME}

To complete the one-time login:
  1. Open the Spotify app on your phone/computer (signed in to your
     Spotify *Premium* account, on the same network as the Pi).
  2. Start playing any track, then open the "Connect to a device" menu.
  3. Select "${GO_LIBRESPOT_DEVICE_NAME}" from the device list.
  4. Audio should switch to the Phoniebox. Credentials are now stored and
     reused after every reboot - you only do this once.

Verify the REST API is up:
    curl http://${GO_LIBRESPOT_API_HOST}:${GO_LIBRESPOT_API_PORT}/status

Check the service / logs:
    systemctl --user status ${SERVICE_NAME}
    journalctl --user -u ${SERVICE_NAME} -f

For Web API search/metadata (Spotify Developer app credentials) and linking
cards to tracks, see documentation/builders/components/spotify.md
------------------------------------------------------------------------
EOF
}

# -----------------------------------------------------------------------------
# Basic verification.
# -----------------------------------------------------------------------------
verify_install() {
    log_info "Verifying installation ..."
    [ -x "${INSTALL_BIN_PATH}" ] || die "go-librespot binary missing at ${INSTALL_BIN_PATH}"
    [ -f "${CONFIG_PATH}" ] || die "Config missing at ${CONFIG_PATH}"
    [ -f "${SERVICE_PATH}" ] || die "Service unit missing at ${SERVICE_PATH}"

    if [ "$(is_service_enabled "${SERVICE_NAME}" --user)" != true ]; then
        die "Service ${SERVICE_NAME} is not enabled."
    fi
    log_info "Verification OK."
}

usage() {
    cat <<EOF
Usage: ./${script_name}

Installs and configures the go-librespot Spotify backend (pinned ${GO_LIBRESPOT_VERSION}).
Run with no arguments. The script is idempotent and can be re-run to update.
EOF
}

main() {
    if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
        usage
        exit 0
    fi

    log_info "Setting up Spotify backend (go-librespot ${GO_LIBRESPOT_VERSION}) ..."
    install_binary
    write_config
    install_service
    verify_install
    print_auth_instructions
    log_info "Done."
}

main "$@"
