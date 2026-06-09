# Hot Helper Discord Bot

A production-grade Discord bot designed for heavy load, stability, and real-world server management. Built with Python 3.11+ and discord.py v2.4+.

## Features

### Core Systems

- **Verification System**: Automated member verification with role assignment and welcome messages
- **Moderation System**: Hierarchical moderation with warnings, kicks, bans, and mutes
- **Mute Approval System**: Approval workflow for long-duration mutes requiring admin/owner authorization
- **Raid Detection & Lockdown**: Real-time raid detection with automatic lockdown and permission restoration
- **Custom Role Management**: Create, assign, and manage self-assignable roles
- **Music System**: Queue-based music playback with state persistence
- **Moderation Recruitment**: Application system for recruiting new moderators
- **Question of the Day**: Daily rotating questions with thread-based discussions
- **Utility Commands**: Polls, rules, server info, and more

### Production Features

- **Structured Logging**: Daily-rotated logs with full tracebacks
- **SQLite Database**: Single-file database with auto-migration
- **Graceful Shutdown**: Automatic state saving on disconnect
- **Auto-Reconnect**: Handles disconnects and reconnects automatically
- **Rate Limiting**: Built-in cooldowns and security checks
- **Error Handling**: Comprehensive error handling with user-friendly messages

## Quick Start

### Prerequisites

- Python 3.11+
- FFmpeg (for music features)
- Discord Bot Token
- Discord User ID (for owner)

### Local Setup

1. **Clone and setup**:
   ```bash
   cd hot-helper
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your DISCORD_TOKEN and OWNER_ID
   ```

3. **Run the bot**:
   ```bash
   python main.py
   ```

4. **Initial setup in Discord**:
   ```
   !setupwizard
   ```

## Commands

### Setup & Configuration

| Command | Description |
|---------|-------------|
| `!setupwizard` | Interactive setup wizard for new servers |
| `!setupcheck` | Verify bot configuration and permissions |
| `!transferownership <@user>` | Transfer bot ownership (owner only) |

### Moderation

| Command | Description |
|---------|-------------|
| `!warn <@user> <situation>` | Warn a user |
| `!kick <@user> <situation>` | Kick a user |
| `!ban <@user> <situation>` | Ban a user |
| `!mute <@user> <duration> <situation>` | Mute a user (5m, 1h, 1d, 1w, 30d, infinite) |
| `!unmute <@user>` | Unmute a user |
| `!warnings <@user>` | View user warnings |
| `!purge <number>` | Delete messages (owner only) |
| `!pendingmutes` | View pending mute approvals |
| `!setmodrole <@role>` | Set the mod role |
| `!setadminrole <@role>` | Set the admin role |

### Verification

| Command | Description |
|---------|-------------|
| `!setupverify` | Post verification embed with button |

### Roles

| Command | Description |
|---------|-------------|
| `/role create <name> [color] [hoist] [mentionable]` | Create a custom role |
| `/role delete <role>` | Delete a role |
| `/role assign <role> <user>` | Assign role to user |
| `/role remove <role> <user>` | Remove role from user |
| `/role selfassign <role>` | Self-assign a role |
| `/role toggle-selfassign <role>` | Toggle self-assign status |
| `/role list` | List all custom roles |
| `/role createdefaults` | Create default starter roles |

### Music

| Command | Description |
|---------|-------------|
| `!play <query/URL>` | Play music from YouTube, SoundCloud, or URL |
| `!skip` | Skip to next song |
| `!stop` | Stop music |
| `!pause` | Pause music |
| `!resume` | Resume music |
| `!queue` | Show music queue |
| `!nowplaying` | Show current song |
| `!volume <1-100>` | Set volume |
| `!loop [off/one/all]` | Set loop mode |

### Raid & Security

| Command | Description |
|---------|-------------|
| `!drill` | Run a raid drill (owner only) |
| `!unlock` | Unlock server after raid (admin/owner) |
| `!setraidsettings <joins> <seconds> <patterns>` | Configure raid detection |

### Recruitment

| Command | Description |
|---------|-------------|
| `!modrecruit` | Post mod recruitment embed |

### Utility

| Command | Description |
|---------|-------------|
| `!poll "<question>" <option1> <option2> [option3] [option4]` | Create a reaction poll |
| `!rules` | Post server rules |
| `!qotd` | Post question of the day |
| `!addqotd <question>` | Add QOTD question (owner only) |
| `!ping` | Check bot latency |
| `!serverinfo` | Get server information |

## Deployment

### Docker (Recommended)

**Local Development**:
```bash
docker-compose up -d
```

**Production with Docker**:
```bash
docker build -t hot-helper .
docker run -d \
  -e DISCORD_TOKEN=your_token \
  -e OWNER_ID=your_id \
  -v hot-helper-data:/app/data \
  -v hot-helper-logs:/app/logs \
  --restart unless-stopped \
  hot-helper
```

### Render (Free Tier)

1. Push code to GitHub
2. Connect GitHub repo to Render
3. Set environment variables:
   - `DISCORD_TOKEN`
   - `OWNER_ID`
4. Deploy from `render.yaml`

**Prevent Spin-Down**:
Add a cron job to ping your service every 5 minutes using [cron-job.org](https://cron-job.org):
```
https://your-render-url.onrender.com/
```

### Railway

1. Push code to GitHub
2. Connect GitHub repo to Railway
3. Set environment variables:
   - `DISCORD_TOKEN`
   - `OWNER_ID`
4. Deploy (Railway auto-detects `railway.json`)

### VPS / Self-Hosted

**Using Systemd**:
```bash
# Copy service file
sudo cp hot-helper.service /etc/systemd/system/

# Enable and start
sudo systemctl enable hot-helper
sudo systemctl start hot-helper

# View logs
sudo journalctl -u hot-helper -f
```

**Using Screen**:
```bash
screen -S hot-helper
python main.py

# Detach: Ctrl+A then D
# Reattach: screen -r hot-helper
```

**Using Tmux**:
```bash
tmux new-session -d -s hot-helper
tmux send-keys -t hot-helper "python main.py" Enter

# View: tmux attach -t hot-helper
```

## Database Schema

The bot uses SQLite with the following tables:

- `config`: Guild configuration (roles, channels, settings)
- `warnings`: User warnings with situations
- `mutes`: Active and historical mutes
- `pending_approvals`: Mutes awaiting approval
- `raid_logs`: Raid detection events
- `custom_roles`: Custom role metadata
- `music_queues`: Saved music queue state
- `qotd`: Question of the day pool
- `applications`: Mod recruitment applications
- `security_logs`: Failed command attempts
- `verification`: Verified members
- `raid_state`: Saved permissions for raid restoration

## Configuration

### Environment Variables

```env
DISCORD_TOKEN=your_bot_token_here
OWNER_ID=your_discord_user_id
DATABASE_URL=sqlite:///data/hot_helper.db
LOG_LEVEL=INFO
```

### In-Server Configuration

Use `!setupwizard` to configure:
1. Log channel
2. Announcement channel
3. Mod role
4. Admin role
5. Application review channel

## Moderation Hierarchy

- **Owner**: Full access, bypasses all approvals
- **Admin**: Can approve mutes 1 week–1 month, can unlock lockdowns
- **Mod**: Can warn/kick/mute up to 1 week, cannot approve long mutes
- **User**: Can self-assign roles, apply for mod

## Raid Detection

The bot automatically detects raids based on:
- **Join Threshold**: >10 joins in 60 seconds (configurable)
- **Pattern Matching**: >5 similar usernames in 30 seconds (configurable)

**Actions on Detection**:
- Auto-ban detected accounts
- Post announcement in announcement channel
- Enable 5-minute lockdown
- Ping all admins and owner
- Log to log channel

**Drill Mode**: `!drill` simulates a raid without banning for testing.

## Logging

Logs are stored in `logs/bot.log` with daily rotation:
- Console output (INFO level by default)
- File output (rotated daily, 7-day retention)
- Full tracebacks for errors
- Structured timestamps

## Error Handling

All commands include:
- Try/except error handling
- User-friendly error messages
- Full tracebacks logged to file
- Rate limiting and cooldowns

## Performance & Stability

- **Async/Await**: Full async implementation for non-blocking operations
- **Connection Pooling**: Efficient database access
- **State Persistence**: Auto-saves queue, permissions, and config
- **Graceful Shutdown**: Saves state on SIGTERM/SIGINT
- **Auto-Reconnect**: Handles Discord disconnects automatically
- **Memory Efficient**: Minimal memory footprint, suitable for shared hosting

## Troubleshooting

### Bot not responding
```bash
!setupcheck
```
Verify all channels and roles are configured correctly.

### Music not playing
- Ensure FFmpeg is installed: `ffmpeg -version`
- Check bot has voice permissions
- Verify you're in a voice channel

### Mutes not working
- Ensure "Muted" role exists and has proper permissions
- Check bot role is above muted role in role hierarchy

### Raid detection not triggering
```bash
!setraidsettings 10 60 5
!drill
```
Test with drill mode first.

## Support & Contributing

For issues or feature requests, refer to the requirements document.

## License

This bot is provided as-is for use in Discord communities.

## Theme

Hot Helper is a Hot Topic fan-made bot with an edgy but clean aesthetic. Not affiliated with Hot Topic Inc.

---

**Built for production. Ready for 10,000+ member servers.**
