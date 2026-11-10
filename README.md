# Local Linphone to English speech translation prototype

This prototype accepts a SIP call from Linphone at extension **100**, then writes
one English text line after each pause in speech. It uses Asterisk EAGI to read the
incoming call audio and self-hosted faster-whisper for translation. No public
phone number, Twilio account, or OpenAI API key is required.

For each speech chunk, the handler uses Urdu (`ur`) or English (`en`) when Whisper
detects either one. If Whisper detects another language, the handler falls back
to Urdu. The handler then uses Whisper's `translate` task to produce English text.
The log records the unrestricted detection and Urdu/English probabilities for
diagnosis. Mixed-language chunks can still contain errors.

## Run from a fresh clone

Requirements: Windows with WSL2, Ubuntu 22.04, Asterisk, Python virtual-environment
support, and an internet connection to install Python packages and download the
Whisper model. Install Asterisk and venv support in Ubuntu if they are not already
installed (for example, `sudo apt update && sudo apt install asterisk python3-venv`).

Clone the repository, then create the private SIP config from the example. From
PowerShell in the cloned project folder:

```powershell
Copy-Item asterisk\pjsip_fyp.conf.example asterisk\pjsip_fyp.conf
notepad asterisk\pjsip_fyp.conf
```

Replace `CHANGE_THIS_PASSWORD` with a private password of your choice and save.
Do not commit `asterisk/pjsip_fyp.conf`; it is excluded by `.gitignore`.

Run the setup script from Ubuntu/WSL. The script installs Python dependencies,
copies the handler and Asterisk configuration, and restarts Asterisk:

In PowerShell, from this folder:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc 'cd /mnt/c/Users/Ahmed\ Asif/Documents/ChatGPT/Fyp && bash setup-wsl.sh'
```

For a different clone path, change the `cd` path to the clone's Windows path
under `/mnt/c`. Pre-download the model before the first call with:

```powershell
wsl -d Ubuntu-22.04 -u root -- runuser -u asterisk -- /opt/fyp-stt-venv/bin/python3 /mnt/c/Users/<WINDOWS-USER>/<PROJECT-PATH>/preload_model.py
```

Then find the Ubuntu IP address:

```powershell
wsl -d Ubuntu-22.04 -- hostname -I
```

In Linphone, choose **Third-Party SIP Account**. Add a SIP account with username `1001`, domain/server
set to the laptop's Wi-Fi IP and port `5062` over UDP, and the password you placed in
`asterisk/pjsip_fyp.conf`. Dial `100`. After the beep, speak and pause. To watch
transcripts in another PowerShell window:

```powershell
wsl -d Ubuntu-22.04 -- tail -f /var/log/asterisk/fyp_transcripts.jsonl
```

The SIP configuration contains a private password and is excluded from Git.
The Ubuntu IP may change after WSL restarts; run `hostname -I` again if Linphone
cannot connect.

WSL mirrored networking lets a phone on the same Wi-Fi reach Asterisk at the
laptop's Wi-Fi address. For phone Linphone, use the laptop Wi-Fi IP rather than
the Ubuntu NAT IP. The SIP port is `5062` over UDP.

On the phone, open Linphone, choose **Third-Party SIP Account**, and enter
username `1001`, the laptop Wi-Fi address as domain/server, the password in
`asterisk/pjsip_fyp.conf`, and UDP transport with port `5062`. Dial `100` or
`sip:100@<laptop-wifi-ip>:5062`. The phone and laptop must be on the same Wi-Fi.
The Windows Hyper-V firewall rules are limited to the current Wi-Fi subnet;
if the laptop joins another network, update those rules.

The first `faster-whisper` run downloads its model. The default is `medium` on CPU.
For a faster but potentially less accurate run, set `FYP_WHISPER_MODEL=small` in the
EAGI environment. The `FYP_SPEECH_RMS` threshold defaults to 450 and can be
adjusted for a noisy microphone. This is a test extension; it only hears the
caller and does not speak back beyond the initial beep.

