import sqlite3
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "history.db"


def init_db():
    """Veritabanını ve tabloları oluştur (yoksa)."""
    conn = sqlite3.connect(DB_PATH)

    # Kullanıcılar tablosu
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL UNIQUE,
            email      TEXT NOT NULL UNIQUE,
            password   TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Analizler tablosu — user_id ile ilişkilendirildi
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            created_at   TEXT NOT NULL,
            brief        TEXT NOT NULL,
            project_type TEXT,
            risk_level   TEXT,
            suggested_min REAL,
            suggested_max REAL,
            proceed      INTEGER,
            result       TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Migration: eksik kolonları ekle
    for col, definition in [
        ("user_id", "INTEGER"),
        ("status", "TEXT DEFAULT NULL"),  # null, applied, won, lost
    ]:
        try:
            conn.execute(f"ALTER TABLE analyses ADD COLUMN {col} {definition}")
        except Exception:
            pass  # zaten varsa geç

    conn.commit()
    conn.close()


# ─── Kullanıcı işlemleri ───────────────────────────────────────────────────────

def create_user(username: str, email: str, password: str) -> dict | None:
    """Yeni kullanıcı oluştur. Başarılıysa user dict döner, hata varsa None."""
    hashed = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
            (username.strip(), email.strip().lower(), hashed,
             datetime.utcnow().strftime("%Y-%m-%d %H:%M")),
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return {"id": user_id, "username": username, "email": email}
    except sqlite3.IntegrityError:
        return None  # username veya email zaten var


def get_user_by_email(email: str) -> dict | None:
    """Email ile kullanıcı bul."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def get_user_by_id(user_id: int) -> dict | None:
    """ID ile kullanıcı bul."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_password(user: dict, password: str) -> bool:
    """Şifre doğrula."""
    return check_password_hash(user["password"], password)


# ─── Analiz işlemleri ─────────────────────────────────────────────────────────

def save_analysis(brief: str, result: dict, user_id: int | None = None):
    """Analiz sonucunu kaydet."""
    r = result.get("requirements", {})
    p = result.get("proposal", {})
    risks = result.get("risks", {})
    pr = p.get("suggested_price_range", {})

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO analyses
           (user_id, created_at, brief, project_type, risk_level,
            suggested_min, suggested_max, proceed, result)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            brief[:300],
            r.get("project_type", ""),
            risks.get("risk_level", ""),
            pr.get("min"),
            pr.get("max"),
            int(bool(risks.get("proceed_recommendation", True))),
            json.dumps(result),
        ),
    )
    conn.commit()
    conn.close()


def update_status(analysis_id: int, status: str, user_id: int | None = None):
    """Analiz durumunu güncelle. status: applied | won | lost | null"""
    valid = {"applied", "won", "lost", None}
    if status not in valid and status != "null":
        return
    actual = None if status == "null" else status
    conn = sqlite3.connect(DB_PATH)
    if user_id:
        conn.execute("UPDATE analyses SET status = ? WHERE id = ? AND user_id = ?",
                     (actual, analysis_id, user_id))
    else:
        conn.execute("UPDATE analyses SET status = ? WHERE id = ?", (actual, analysis_id))
    conn.commit()
    conn.close()


def delete_analysis(analysis_id: int, user_id: int | None = None):
    """Belirli bir analizi sil. user_id verilmişse sadece o kullanıcının analizini siler."""
    conn = sqlite3.connect(DB_PATH)
    if user_id:
        conn.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?",
                     (analysis_id, user_id))
    else:
        conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
    conn.commit()
    conn.close()


def get_stats(user_id: int) -> dict:
    """Kullanıcının analiz istatistiklerini hesapla."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT project_type, risk_level, suggested_min, suggested_max, status, result FROM analyses WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()

    total = len(rows)
    applied = sum(1 for r in rows if r["status"] in ("applied", "won", "lost"))
    won = sum(1 for r in rows if r["status"] == "won")
    lost = sum(1 for r in rows if r["status"] == "lost")
    win_rate = round(won / applied * 100) if applied > 0 else 0

    # Proje tipine göre kazanma sayısı
    type_wins: dict = {}
    type_counts: dict = {}
    for r in rows:
        pt = r["project_type"] or "Unknown"
        type_counts[pt] = type_counts.get(pt, 0) + 1
        if r["status"] == "won":
            type_wins[pt] = type_wins.get(pt, 0) + 1

    best_type = max(type_wins, key=type_wins.get) if type_wins else None

    # Ortalama apply skoru
    scores = []
    for r in rows:
        try:
            result = json.loads(r["result"])
            s = result.get("proposal", {}).get("apply_score", {}).get("score")
            if s is not None:
                scores.append(s)
        except Exception:
            pass
    avg_score = round(sum(scores) / len(scores)) if scores else None

    return {
        "total": total,
        "applied": applied,
        "won": won,
        "lost": lost,
        "pending": applied - won - lost,
        "win_rate": win_rate,
        "best_type": best_type,
        "avg_score": avg_score,
    }


def get_recent(limit: int = 5, user_id: int | None = None) -> list:
    """Son N analizi döndür. user_id verilmişse sadece o kullanıcının analizlerini getirir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if user_id:
        rows = conn.execute(
            """SELECT id, created_at, project_type, risk_level,
                      suggested_min, suggested_max, proceed, status, result
               FROM analyses WHERE user_id = ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, created_at, project_type, risk_level,
                      suggested_min, suggested_max, proceed, status, result
               FROM analyses
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    conn.close()
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "project_type": row["project_type"],
            "risk_level": row["risk_level"],
            "suggested_min": row["suggested_min"],
            "suggested_max": row["suggested_max"],
            "proceed": bool(row["proceed"]),
            "status": row["status"],
            "result": json.loads(row["result"]),
        }
        for row in rows
    ]
