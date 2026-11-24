#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
project_dir=$PWD
target=/opt/kaavish-demo
sip_config=asterisk/pjsip_fyp.conf
model_cache=tmp/whisper-models/models--Systran--faster-whisper-medium

if [[ ! -f "$sip_config" ]]; then (
    umask 077
    sip_password=$(openssl rand -hex 16)
    sed "s/CHANGE_THIS_PASSWORD/$sip_password/" asterisk/pjsip_fyp.conf.example > "$sip_config"
); fi
if grep -q CHANGE_THIS_PASSWORD "$sip_config"; then
    echo "Set a private SIP password in $sip_config before continuing." >&2
    exit 1
fi

test -x .venv/bin/python
test -d "$model_cache/snapshots"
sudo -v
sudo install -d -m 755 "$target" "$target/venv" "$target/models"
sudo cp -a --no-preserve=ownership .venv/. "$target/venv/"
sudo cp -a --no-preserve=ownership "$model_cache" "$target/models/"
sudo install -m 644 intent_classifier.py intent_examples.json test_pipeline.py \
    /usr/share/asterisk/agi-bin/
sudo install -m 755 asterisk/fyp_live.py /usr/share/asterisk/agi-bin/fyp_live.py
sudo install -d -m 700 -o asterisk -g asterisk /var/spool/asterisk/kaavish

psql -X -w -v ON_ERROR_STOP=1 -d kaavish_demo -f "$project_dir/test_calls.sql"
sudo -u postgres psql -X -w -v ON_ERROR_STOP=1 -d kaavish_demo <<'SQL'
SELECT 'CREATE ROLE asterisk LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'asterisk')
\gexec
GRANT CONNECT ON DATABASE kaavish_demo TO asterisk;
GRANT USAGE ON SCHEMA public TO asterisk;
GRANT INSERT ON TABLE test_calls TO asterisk;
GRANT USAGE ON SEQUENCE test_calls_id_seq TO asterisk;
SQL

sudo install -m 640 -o root -g asterisk "$sip_config" /etc/asterisk/pjsip_fyp.conf
sudo install -m 644 asterisk/extensions_live.conf /etc/asterisk/extensions_fyp.conf
for config in pjsip extensions; do
    include="#include ${config}_fyp.conf"
    if ! sudo grep -Fxq "$include" "/etc/asterisk/$config.conf"; then
        printf '\n%s\n' "$include" | sudo tee -a "/etc/asterisk/$config.conf" >/dev/null
    fi
done
sudo systemctl restart asterisk
sudo asterisk -rx 'pjsip show endpoint 1001'
sudo asterisk -rx 'dialplan show 100@fyp-internal'
