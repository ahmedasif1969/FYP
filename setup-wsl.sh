#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$repo_dir/asterisk/pjsip_fyp.conf" ]]; then
    echo "Missing private SIP config: $repo_dir/asterisk/pjsip_fyp.conf" >&2
    echo "Copy pjsip_fyp.conf.example to pjsip_fyp.conf and replace CHANGE_THIS_PASSWORD." >&2
    exit 1
fi
sudo python3 -m venv /opt/fyp-stt-venv
sudo /opt/fyp-stt-venv/bin/pip install -r "$repo_dir/requirements.txt"
sudo install -m 755 "$repo_dir/transcribe_call.py" /usr/share/asterisk/agi-bin/fyp_transcribe.py
sudo install -m 644 "$repo_dir/asterisk/pjsip_fyp.conf" /etc/asterisk/pjsip_fyp.conf
sudo install -m 644 "$repo_dir/asterisk/extensions_fyp.conf" /etc/asterisk/extensions_fyp.conf
sudo touch /var/log/asterisk/fyp_transcripts.jsonl
sudo chown asterisk:asterisk /var/log/asterisk/fyp_transcripts.jsonl
sudo install -d -o asterisk -g asterisk /var/cache/asterisk/fyp-whisper
sudo grep -q '^#include pjsip_fyp.conf$' /etc/asterisk/pjsip.conf || echo '#include pjsip_fyp.conf' | sudo tee -a /etc/asterisk/pjsip.conf >/dev/null
sudo grep -q '^#include extensions_fyp.conf$' /etc/asterisk/extensions.conf || echo '#include extensions_fyp.conf' | sudo tee -a /etc/asterisk/extensions.conf >/dev/null
sudo sed -i '1c#!/opt/fyp-stt-venv/bin/python3' /usr/share/asterisk/agi-bin/fyp_transcribe.py
sudo service asterisk restart
sudo asterisk -rx 'pjsip show endpoint 1001'
sudo asterisk -rx 'dialplan show 100@fyp-internal'
