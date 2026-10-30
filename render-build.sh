#!/usr/bin/env bash
set -o errexit

mkdir -p bin

# 1. Tải FFmpeg và FFprobe static
echo "Downloading ffmpeg..."
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz
mv ffmpeg-*-amd64-static/ffmpeg bin/
mv ffmpeg-*-amd64-static/ffprobe bin/
rm -rf ffmpeg.tar.xz ffmpeg-*-amd64-static

# 2. Tải Node.js static để yt-dlp giải mã n-challenge của YouTube
echo "Downloading Node.js..."
curl -L https://nodejs.org/dist/v20.11.0/node-v20.11.0-linux-x64.tar.xz -o node.tar.xz
tar -xf node.tar.xz
mv node-v*-linux-x64/bin/node bin/
rm -rf node.tar.xz node-v*-linux-x64

# Quan trọng: Cấp quyền thực thi cho toàn bộ file trong thư mục bin/
chmod +x bin/*

echo "Setup FFmpeg and Node.js successfully!"