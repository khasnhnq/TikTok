#!/usr/bin/env bash
set -o errexit

mkdir -p bin

# 1. Tải FFmpeg static
echo "Downloading ffmpeg..."
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz
mv ffmpeg-*-amd64-static/ffmpeg bin/
mv ffmpeg-*-amd64-static/ffprobe bin/
rm -rf ffmpeg.tar.xz ffmpeg-*-amd64-static

# 2. Cài đặt Node.js trực tiếp qua apt-get (hoặc tải bản binary chuẩn)
echo "Installing Node.js..."
node_version="v20.11.0"
curl -O https://nodejs.org/dist/$node_version/node-$node_version-linux-x64.tar.xz
tar -xf node-$node_version-linux-x64.tar.xz
cp node-$node_version-linux-x64/bin/node bin/
rm -rf node-$node_version-linux-x64.tar.xz node-$node_version-linux-x64

chmod +x bin/*
echo "Setup completed successfully!"