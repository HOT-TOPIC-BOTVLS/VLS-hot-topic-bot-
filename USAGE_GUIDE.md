# 📖 Hot Helper Bot - Final Usage Guide

The **Hot Helper** bot is a high-performance, production-ready Discord management system. This guide explains how to use its core features and commands.

---

## 🛠️ Initial Setup

### 1. Bot Activation
Run the bot using `python main.py`. Once online, use the interactive wizard:
- **Command**: `!setupwizard`
- **Steps**:
  1. Set **Log Channel** (for moderation and system logs)
  2. Set **Announcement Channel** (for raid alerts and news)
  3. Set **Mod Role** (permission to warn/kick/mute)
  4. Set **Admin Role** (permission to approve long mutes and unlock server)
  5. Set **Application Channel** (where mod applications go)

### 2. Verification
To set up a "Click to Verify" system:
- **Command**: `!setupverify`
- **Effect**: Posts an embed with a "Verify" button. Clicking assigns the verified role automatically.

---

## 🛡️ Moderation System

The bot uses a **Hierarchical Permission System**:
- **Owner**: Bypasses all restrictions.
- **Admin**: Can approve mutes (1w-30d) and unlock the server.
- **Mod**: Can warn, kick, and mute (up to 1w).

### Key Commands:
| Command | Usage | Description |
|---------|-------|-------------|
| `!warn` | `!warn @user <reason>` | Issues a warning and logs it. |
| `!mute` | `!mute @user <time> <reason>` | Mutes user (e.g., `5m`, `1h`, `1d`). |
| `!unmute` | `!unmute @user` | Removes mute role. |
| `!kick` | `!kick @user <reason>` | Kicks user from server. |
| `!ban` | `!ban @user <reason>` | Permanently bans user. |
| `!warnings`| `!warnings @user` | Shows user's warning history. |

---

## 🚨 Raid Detection & Security

The bot monitors join rates and username patterns automatically.

- **Detection**: Triggers if >10 joins occur in 60s or >5 similar names join.
- **Action**: Automatically bans offenders, locks down the server, and pings admins.
- **Testing**: Use `!drill` to simulate a raid (doesn't ban).
- **Recovery**: Use `!unlock` to restore normal permissions.

---

## 🎵 Music System

State-of-the-art music playback with persistence.

- `!play <url/search>`: Plays music from YouTube/SoundCloud.
- `!queue`: Shows the current list.
- `!skip`, `!stop`, `!pause`, `!resume`: Standard controls.
- `!loop [off/one/all]`: Sets looping mode.
- **Persistence**: If the bot restarts, it remembers the queue and volume!

---

## 👥 Roles & Recruitment

### Custom Roles
- `/role create <name> <color>`: Create a new role.
- `/role selfassign <role>`: Make a role self-assignable by users.
- `/role list`: See all available custom roles.

### Mod Recruitment
- `!modrecruit`: Posts a recruitment embed.
- **Workflow**: Users click "Apply" -> Fill out a Modal form -> Admins review in the app channel.

---

## ❓ Question of the Day (QOTD)

- **Command**: `!qotd`
- **Automation**: Automatically posts a new question every day at 10 AM UTC.
- **Discussion**: Creates a thread for every question to keep the main chat clean.

---

## 🔧 Technical Commands

- `!setupcheck`: Diagnostic tool to verify bot permissions and channel setups.
- `!ping`: Check bot latency.
- `!serverinfo`: Get detailed server statistics.

---

**Built for performance. Tested to the max.**
