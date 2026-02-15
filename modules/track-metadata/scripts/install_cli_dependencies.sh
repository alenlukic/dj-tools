#!/usr/bin/env bash

set -euo pipefail

FFMPEG_URL="https://ffmpeg.org/download.html"

function info() {
  printf '\033[1;34m[info]\033[0m %s\n' "$1"
}

function warn() {
  printf '\033[1;33m[warn]\033[0m %s\n' "$1"
}

function error() {
  printf '\033[1;31m[error]\033[0m %s\n' "$1"
}

function ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    info "ffmpeg already installed"
    return 0
  fi

  local uname_out
  uname_out="$(uname -s)"

  case "$uname_out" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        info "Installing ffmpeg via Homebrew"
        brew install ffmpeg
      else
        warn "Homebrew not found. Install Homebrew (https://brew.sh) then rerun this script or install ffmpeg manually from $FFMPEG_URL"
        return 1
      fi
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        info "Installing ffmpeg via apt"
        sudo apt-get update
        sudo apt-get install -y ffmpeg
      elif command -v dnf >/dev/null 2>&1; then
        info "Installing ffmpeg via dnf"
        sudo dnf install -y ffmpeg
      elif command -v pacman >/dev/null 2>&1; then
        info "Installing ffmpeg via pacman"
        sudo pacman -Sy --noconfirm ffmpeg
      else
        warn "Unsupported package manager. Install ffmpeg manually from $FFMPEG_URL"
        return 1
      fi
      ;;
    *)
      warn "Unsupported platform ($uname_out). Install ffmpeg manually from $FFMPEG_URL"
      return 1
      ;;
  esac

  if command -v ffmpeg >/dev/null 2>&1; then
    info "ffmpeg installation verified"
  else
    error "ffmpeg installation failed"
    return 1
  fi
}

function main() {
  info "Ensuring CLI dependencies are installed"
  ensure_ffmpeg
  info "All CLI dependencies verified"
}

main "$@"

