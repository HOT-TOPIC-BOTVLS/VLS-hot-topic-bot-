"""Database management for Hot Helper bot."""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from config import DB_PATH

class Database:
    """SQLite database handler."""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Config table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                guild_id INTEGER PRIMARY KEY,
                mod_role_id INTEGER,
                admin_role_id INTEGER,
                log_channel_id INTEGER,
                announce_channel_id INTEGER,
                app_channel_id INTEGER,
                owner_id INTEGER,
                raid_join_threshold INTEGER DEFAULT 10,
                raid_window INTEGER DEFAULT 60,
                raid_pattern_count INTEGER DEFAULT 5,
                raid_action TEXT DEFAULT 'ban',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Warnings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                number INTEGER NOT NULL,
                situation TEXT NOT NULL,
                mod_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_warnings_user_guild ON warnings (user_id, guild_id)")
        
        # Mutes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                duration INTEGER,
                reason TEXT NOT NULL,
                mod_id INTEGER NOT NULL,
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                active INTEGER DEFAULT 1,
                approved_by INTEGER
            )
        """)
        
        # Pending approvals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                duration INTEGER,
                reason TEXT NOT NULL,
                mod_id INTEGER NOT NULL,
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                approver_id INTEGER,
                message_id INTEGER
            )
        """)
        
        # Raid logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raid_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                triggered_by INTEGER,
                action_taken TEXT NOT NULL,
                users_affected TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_drill INTEGER DEFAULT 0
            )
        """)
        
        # Custom roles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                is_self_assignable INTEGER DEFAULT 0,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Music queues table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS music_queues (
                guild_id INTEGER PRIMARY KEY,
                queue_data_json TEXT,
                current_song_json TEXT,
                is_paused INTEGER DEFAULT 0,
                volume INTEGER DEFAULT 100,
                loop_mode TEXT DEFAULT 'off',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # QOTD table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qotd (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                used_at TIMESTAMP
            )
        """)
        
        # Applications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                answers_json TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reviewer_id INTEGER,
                reviewed_at TIMESTAMP
            )
        """)
        
        # Security logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                attempt_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Verification table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Raid state table (for lockdown restoration)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raid_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL UNIQUE,
                permissions_json TEXT NOT NULL,
                locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # XP and Leveling tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_xp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                total_xp INTEGER DEFAULT 0,
                last_xp_gain TIMESTAMP,
                UNIQUE(user_id, guild_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS level_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                level INTEGER NOT NULL,
                reward_type TEXT,
                reward_value TEXT,
                UNIQUE(guild_id, level)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                messages_sent INTEGER DEFAULT 0,
                reactions_given INTEGER DEFAULT 0,
                voice_minutes INTEGER DEFAULT 0,
                UNIQUE(user_id, guild_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    # Config methods
    def get_guild_config(self, guild_id):
        """Get guild configuration."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM config WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def set_guild_config(self, guild_id, **kwargs):
        """Set guild configuration."""
        if guild_id is None:
            raise ValueError("guild_id cannot be None")
            
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            config = self.get_guild_config(guild_id)
            if config:
                updates = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [guild_id]
                cursor.execute(f"UPDATE config SET {updates} WHERE guild_id = ?", values)
            else:
                keys = ", ".join(kwargs.keys())
                placeholders = ", ".join(["?"] * len(kwargs))
                values = list(kwargs.values())
                cursor.execute(f"INSERT INTO config (guild_id, {keys}) VALUES (?, {placeholders})", [guild_id] + values)
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # Warning methods
    def add_warning(self, user_id, guild_id, situation, mod_id):
        """Add a warning for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get next warning number
        cursor.execute("SELECT COUNT(*) as count FROM warnings WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        count = cursor.fetchone()["count"]
        number = count + 1
        
        cursor.execute("""
            INSERT INTO warnings (user_id, guild_id, type, number, situation, mod_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, guild_id, "warn", number, situation, mod_id))
        
        conn.commit()
        conn.close()
        return number
    
    def get_warnings(self, user_id, guild_id, limit=50):
        """Get warnings for a user in a guild, limited to prevent overflow."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, guild_id, limit))
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]
    
    # Mute methods
    def add_mute(self, user_id, guild_id, duration, reason, mod_id, expires_at=None):
        """Add a mute for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mutes (user_id, guild_id, duration, reason, mod_id, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, guild_id, duration, reason, mod_id, expires_at))
        conn.commit()
        mute_id = cursor.lastrowid
        conn.close()
        return mute_id
    
    def get_active_mute(self, user_id, guild_id):
        """Get active mute for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM mutes WHERE user_id = ? AND guild_id = ? AND active = 1
            ORDER BY issued_at DESC LIMIT 1
        """, (user_id, guild_id))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def unmute_user(self, user_id, guild_id):
        """Unmute a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE mutes SET active = 0 WHERE user_id = ? AND guild_id = ? AND active = 1
        """, (user_id, guild_id))
        conn.commit()
        conn.close()
    
    def get_expired_mutes(self):
        """Get all expired mutes."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM mutes WHERE active = 1 AND expires_at IS NOT NULL AND expires_at <= datetime('now')
        """)
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]
    
    # Pending approval methods
    def add_pending_approval(self, user_id, guild_id, approval_type, duration, reason, mod_id):
        """Add a pending approval."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pending_approvals (user_id, guild_id, type, duration, reason, mod_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, guild_id, approval_type, duration, reason, mod_id))
        conn.commit()
        approval_id = cursor.lastrowid
        conn.close()
        return approval_id
    
    def get_pending_approvals(self, guild_id):
        """Get all pending approvals for a guild."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM pending_approvals WHERE guild_id = ? AND status = 'pending'
            ORDER BY issued_at DESC
        """, (guild_id,))
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]
    
    def approve_mute(self, approval_id, approver_id):
        """Approve a pending mute."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pending_approvals SET status = 'approved', approver_id = ?
            WHERE id = ?
        """, (approver_id, approval_id))
        conn.commit()
        conn.close()
    
    def deny_mute(self, approval_id, approver_id):
        """Deny a pending mute."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pending_approvals SET status = 'denied', approver_id = ?
            WHERE id = ?
        """, (approver_id, approval_id))
        conn.commit()
        conn.close()
    
    def get_mod_logs(self, user_id, guild_id, limit=50):
        """Get combined moderation history for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        logs = []
        
        # Get warnings
        cursor.execute(
            "SELECT 'warning' as type, timestamp, situation as reason, mod_id FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, guild_id, limit)
        )
        for row in cursor.fetchall():
            logs.append({"type": "warning", "timestamp": row[1], "reason": row[2], "mod_id": row[3]})
        
        # Get mutes
        cursor.execute(
            "SELECT 'mute' as type, issued_at, reason, mod_id FROM mutes WHERE user_id = ? AND guild_id = ? AND active = 1 ORDER BY issued_at DESC LIMIT ?",
            (user_id, guild_id, limit)
        )
        for row in cursor.fetchall():
            logs.append({"type": "mute", "timestamp": row[1], "reason": row[2], "mod_id": row[3]})
        
        conn.close()
        
        # Sort by timestamp descending
        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        return logs[:limit]
    
    # XP and Leveling methods
    def add_xp(self, user_id, guild_id, xp_amount):
        """Add XP to a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get or create user XP record
            cursor.execute("SELECT * FROM user_xp WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            record = cursor.fetchone()
            
            if record:
                new_xp = record["xp"] + xp_amount
                new_total = record["total_xp"] + xp_amount
                
                # Check for level up (100 XP per level)
                old_level = record["level"]
                new_level = (new_total // 100) + 1
                
                cursor.execute("""
                    UPDATE user_xp SET xp = ?, total_xp = ?, level = ?, last_xp_gain = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND guild_id = ?
                """, (new_xp, new_total, new_level, user_id, guild_id))
                
                leveled_up = new_level > old_level
            else:
                cursor.execute("""
                    INSERT INTO user_xp (user_id, guild_id, xp, total_xp, level, last_xp_gain)
                    VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (user_id, guild_id, xp_amount, xp_amount))
                leveled_up = False
            
            conn.commit()
            return leveled_up
        finally:
            conn.close()
    
    def get_user_xp(self, user_id, guild_id):
        """Get user XP and level."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_xp WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def get_leaderboard(self, guild_id, limit=10):
        """Get top users by level and XP."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, level, total_xp FROM user_xp 
            WHERE guild_id = ? 
            ORDER BY level DESC, total_xp DESC 
            LIMIT ?
        """, (guild_id, limit))
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]
    
    def get_user_rank(self, user_id, guild_id):
        """Get user's rank in guild."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as rank FROM user_xp 
            WHERE guild_id = ? AND (level > (SELECT level FROM user_xp WHERE user_id = ? AND guild_id = ?)
            OR (level = (SELECT level FROM user_xp WHERE user_id = ? AND guild_id = ?) 
            AND total_xp > (SELECT total_xp FROM user_xp WHERE user_id = ? AND guild_id = ?)))
        """, (guild_id, user_id, guild_id, user_id, guild_id, user_id, guild_id))
        result = cursor.fetchone()
        conn.close()
        return result["rank"] + 1 if result else 1
    
    def add_user_stat(self, user_id, guild_id, stat_type, amount=1):
        """Add to user statistics."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM user_stats WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            record = cursor.fetchone()
            
            if record:
                if stat_type == "messages":
                    new_val = record["messages_sent"] + amount
                    cursor.execute("UPDATE user_stats SET messages_sent = ? WHERE user_id = ? AND guild_id = ?", (new_val, user_id, guild_id))
                elif stat_type == "reactions":
                    new_val = record["reactions_given"] + amount
                    cursor.execute("UPDATE user_stats SET reactions_given = ? WHERE user_id = ? AND guild_id = ?", (new_val, user_id, guild_id))
                elif stat_type == "voice":
                    new_val = record["voice_minutes"] + amount
                    cursor.execute("UPDATE user_stats SET voice_minutes = ? WHERE user_id = ? AND guild_id = ?", (new_val, user_id, guild_id))
            else:
                if stat_type == "messages":
                    cursor.execute("INSERT INTO user_stats (user_id, guild_id, messages_sent) VALUES (?, ?, ?)", (user_id, guild_id, amount))
                elif stat_type == "reactions":
                    cursor.execute("INSERT INTO user_stats (user_id, guild_id, reactions_given) VALUES (?, ?, ?)", (user_id, guild_id, amount))
                elif stat_type == "voice":
                    cursor.execute("INSERT INTO user_stats (user_id, guild_id, voice_minutes) VALUES (?, ?, ?)", (user_id, guild_id, amount))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_user_stats(self, user_id, guild_id):
        """Get user statistics."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_stats WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
        # Music queue methods
    def save_music_queue(self, guild_id, queue_data, current_song, is_paused, volume, loop_mode):
        """Save music queue state."""
        # Limit queue size to 500 to prevent database bloat
        if len(queue_data) > 500:
            queue_data = queue_data[:500]
            
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            queue_json = json.dumps(queue_data)
            current_json = json.dumps(current_song) if current_song else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO music_queues 
                (guild_id, queue_data_json, current_song_json, is_paused, volume, loop_mode)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, queue_json, current_json, 1 if is_paused else 0, volume, loop_mode))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_music_queue(self, guild_id):
        """Get saved music queue state."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM music_queues WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                "queue": json.loads(result["queue_data_json"]) if result["queue_data_json"] else [],
                "current_song": json.loads(result["current_song_json"]) if result["current_song_json"] else None,
                "is_paused": bool(result["is_paused"]),
                "volume": result["volume"],
                "loop_mode": result["loop_mode"]
            }
        return None
    
    # QOTD methods
    def add_qotd(self, question):
        """Add a QOTD question."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO qotd (question) VALUES (?)", (question,))
        conn.commit()
        conn.close()
    
    def get_random_qotd(self):
        """Get a random unused QOTD question."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM qotd WHERE used = 0 ORDER BY RANDOM() LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def mark_qotd_used(self, question_id):
        """Mark a QOTD question as used."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE qotd SET used = 1, used_at = CURRENT_TIMESTAMP WHERE id = ?", (question_id,))
        conn.commit()
        conn.close()
    
    def reset_qotd(self):
        """Reset all QOTD questions as unused."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE qotd SET used = 0, used_at = NULL")
        conn.commit()
        conn.close()
    
    # Custom roles methods
    def add_custom_role(self, guild_id, role_id, name, created_by):
        """Add a custom role."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO custom_roles (guild_id, role_id, name, created_by)
            VALUES (?, ?, ?, ?)
        """, (guild_id, role_id, name, created_by))
        conn.commit()
        conn.close()
    
    def get_custom_roles(self, guild_id):
        """Get all custom roles for a guild."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_roles WHERE guild_id = ? ORDER BY created_at DESC", (guild_id,))
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]
    
    def toggle_self_assign(self, role_id, guild_id):
        """Toggle self-assignable status for a role."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE custom_roles SET is_self_assignable = 1 - is_self_assignable
            WHERE role_id = ? AND guild_id = ?
        """, (role_id, guild_id))
        conn.commit()
        conn.close()
    
    # Verification methods
    def add_verification(self, user_id, guild_id):
        """Add a verification record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO verification (user_id, guild_id)
            VALUES (?, ?)
        """, (user_id, guild_id))
        conn.commit()
        conn.close()
    
    def is_verified(self, user_id, guild_id):
        """Check if user is verified."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM verification WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    # Raid state methods
    def save_raid_state(self, guild_id, permissions_json):
        """Save raid state for restoration."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO raid_state (guild_id, permissions_json)
            VALUES (?, ?)
        """, (guild_id, permissions_json))
        conn.commit()
        conn.close()
    
    def get_raid_state(self, guild_id):
        """Get saved raid state."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM raid_state WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def clear_raid_state(self, guild_id):
        """Clear raid state."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM raid_state WHERE guild_id = ?", (guild_id,))
        conn.commit()
        conn.close()

