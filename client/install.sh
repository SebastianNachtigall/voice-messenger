#!/bin/bash
# Voice Messenger - Installation Script for Raspberry Pi Zero

set -e

echo "🚀 Voice Messenger Installation"
echo "================================"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "📦 Updating system..."
sudo apt-get update

# Install dependencies
echo "📦 Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    portaudio19-dev \
    python3-pyaudio \
    alsa-utils

# Install Python packages
echo "🐍 Installing Python packages..."
pip3 install --user -r requirements.txt

# Create audio directory
echo "📁 Creating directories..."
mkdir -p audio_messages

# Test audio
echo ""
echo "🎤 Testing audio devices..."
echo "Available recording devices:"
arecord -l
echo ""
echo "Available playback devices:"
aplay -l
echo ""

# Configure audio (optional)
read -p "Configure audio settings now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Opening alsamixer (use F6 to select device, arrow keys to adjust, ESC to exit)"
    sleep 2
    alsamixer
fi

# Create example config
if [ ! -f config.json ]; then
    echo "📝 Creating example configuration..."
    python3 config.py
    echo "✅ Example config.json created"
    echo "   Please edit config.json to configure your device!"
else
    echo "ℹ️  config.json already exists, keeping it"
fi

# Offer to create systemd service
echo ""
read -p "Create systemd service for auto-start? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/etc/systemd/system/voice-messenger.service"
    INSTALL_DIR=$(pwd)
    
    echo "Creating systemd service..."
    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Voice Messenger
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable voice-messenger
    
    echo "✅ Service created and enabled"
    echo "   Start with: sudo systemctl start voice-messenger"
    echo "   Status: sudo systemctl status voice-messenger"
    echo "   Logs: sudo journalctl -u voice-messenger -f"
fi

# Test recording
echo ""
read -p "Test recording and playback? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Recording 3 seconds... Speak now!"
    arecord -d 3 -f cd test_recording.wav
    echo "Playing back..."
    aplay test_recording.wav
    rm test_recording.wav
    echo "✅ Audio test complete"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit config.json with your device settings"
echo "2. Configure friends and GPIO pins"
echo "3. Connect hardware (buttons, LEDs, mic, speaker)"
echo "4. Run: python3 main.py"
echo ""
echo "For auto-start, use: sudo systemctl start voice-messenger"
echo ""
