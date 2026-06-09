# Hot Helper Bot - Quick Start Guide

## Setup (5 minutes)

### 1. Prerequisites
- Python 3.11+
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- Your Discord User ID
- FFmpeg (for music features)

### 2. Local Installation

```bash
# Clone/download the bot
cd hot-helper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your DISCORD_TOKEN and OWNER_ID
```

### 3. Run the Bot

```bash
python main.py
```

You should see:
```
2026-06-09 02:00:00 - hot_helper - INFO - Bot logged in as Hot Helper#1234
```

### 4. Configure in Discord

In your Discord server:
```
!setupwizard
```

Follow the prompts to set:
1. Log channel
2. Announcement channel
3. Mod role
4. Admin role
5. Application review channel

### 5. Test It

```
!setupcheck          # Verify configuration
!setupverify         # Post verification button
!rules               # Post rules
!modrecruit          # Post mod recruitment
```

## Common Commands

### Moderation
```
!warn @user situation           # Warn a user
!mute @user 1h reason           # Mute for 1 hour
!kick @user reason              # Kick user
!ban @user reason               # Ban user
!warnings @user                 # View warnings
```

### Verification
```
!setupverify                    # Post verification embed
```

### Roles
```
/role create MyRole #FF0000     # Create role
/role selfassign MyRole         # Self-assign role
/role list                      # List roles
```

### Music
```
!play https://youtube.com/...   # Play song
!skip                           # Skip
!queue                          # Show queue
!volume 50                      # Set volume
```

### Raid & Security
```
!drill                          # Test raid detection
!unlock                         # End lockdown
!setraidsettings 10 60 5        # Configure raid detection
```

## Deployment

### Docker (Recommended)
```bash
docker-compose up -d
```

### Render (Free)
1. Push to GitHub
2. Connect to Render
3. Set `DISCORD_TOKEN` and `OWNER_ID` env vars
4. Deploy

### Railway
1. Push to GitHub
2. Connect to Railway
3. Set env vars
4. Deploy

### VPS
```bash
sudo cp hot-helper.service /etc/systemd/system/
sudo systemctl enable hot-helper
sudo systemctl start hot-helper
```

## Troubleshooting

**Bot not responding?**
```
!setupcheck
```

**Mutes not working?**
- Check "Muted" role exists
- Ensure bot role is above it

**Music not playing?**
- Install FFmpeg: `apt-get install ffmpeg`
- Check bot has voice permissions

**Raid detection not working?**
```
!drill              # Test with drill mode
!setraidsettings 10 60 5
```

## Support

Refer to README.md for full documentation and troubleshooting.

---

**You're all set! Happy moderating! 🎉**
