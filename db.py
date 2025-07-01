import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

def _get_time_period(period: str) -> datetime:
    """Helper function to get datetime for a given period"""
    now = datetime.now()
    if period == "today":
        return now - timedelta(hours=24)
    elif period == "week":
        return now - timedelta(days=7)
    elif period == "month":
        return now - timedelta(days=30)
    return now - timedelta(days=365)

def init_db():
    """Initialize the database with required tables"""
    with sqlite3.connect("data.db") as con:
        # Create main complaints table
        con.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            description TEXT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            image TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
        """)

        # Create completed complaints archive
        con.execute("""
        CREATE TABLE IF NOT EXISTS completed_complaints (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            description TEXT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            image TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            status_before TEXT NOT NULL,
            processing_time TEXT NOT NULL,
            admin_notes TEXT DEFAULT ''
        )
        """)

        # Create processing history log
        con.execute("""
        CREATE TABLE IF NOT EXISTS processing_history (
            id INTEGER PRIMARY KEY,
            complaint_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            admin_user TEXT NOT NULL,
            FOREIGN KEY(complaint_id) REFERENCES complaints(id)
        )
        """)

def add_complaint(
    category: str,
    description: str,
    full_name: str,
    phone: str,
    lat: float,
    lng: float,
    image: str
) -> None:
    """Add a new complaint to the database"""
    with sqlite3.connect("data.db") as con:
        con.execute("""
        INSERT INTO complaints
        (category, description, full_name, phone, lat, lng, image, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (category, description, full_name, phone, lat, lng, image))

def get_all_complaints(period: Optional[str] = None) -> List[sqlite3.Row]:
    """Get all complaints with optional time period filter"""
    with sqlite3.connect("data.db") as con:
        query = "SELECT * FROM complaints"
        params = []
        
        if period:
            since = _get_time_period(period)
            query += " WHERE datetime(created_at) > ?"
            params.append(since.isoformat())
            
        query += " ORDER BY created_at DESC"
        con.row_factory = sqlite3.Row
        return con.execute(query, tuple(params)).fetchall()

def get_complaints_by_status(status: str, period: Optional[str] = None) -> List[sqlite3.Row]:
    """Get complaints filtered by status and optional time period"""
    with sqlite3.connect("data.db") as con:
        query = "SELECT * FROM complaints WHERE status = ?"
        params = [status]
        
        if period:
            since = _get_time_period(period)
            query += " AND datetime(created_at) > ?"
            params.append(since.isoformat())
            
        query += " ORDER BY created_at DESC"
        con.row_factory = sqlite3.Row
        return con.execute(query, tuple(params)).fetchall()
    


def get_completed_complaints(period: Optional[str] = None) -> List[sqlite3.Row]:
    """Get completed complaints with optional time period filter"""
    with sqlite3.connect("data.db") as con:
        query = "SELECT * FROM completed_complaints"
        params = []
        
        if period:
            since = _get_time_period(period)
            query += " WHERE datetime(completed_at) > ?"
            params.append(since.isoformat())
            
        query += " ORDER BY completed_at DESC"
        con.row_factory = sqlite3.Row
        return con.execute(query, tuple(params)).fetchall()

def update_complaint_status(complaint_id: int, status: str, admin_user: str = "admin") -> None:
    """Update complaint status and log the change"""
    with sqlite3.connect("data.db") as con:
        # Update status
        con.execute("UPDATE complaints SET status = ? WHERE id = ?", (status, complaint_id))
        
        # Log the status change
        con.execute("""
        INSERT INTO processing_history
        (complaint_id, status, changed_at, admin_user)
        VALUES (?, ?, datetime('now'), ?)
        """, (complaint_id, status, admin_user))

def move_to_completed(complaint_id: int, admin_notes: str = "") -> None:
    """Move a complaint to completed status"""
    with sqlite3.connect("data.db") as con:
        # Get the complaint
        complaint = con.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,)).fetchone()
        if not complaint:
            return
            
        # Calculate processing time
        created_at = datetime.strptime(complaint[8], "%Y-%m-%d %H:%M:%S")
        processing_time = str(datetime.now() - created_at)
        
        # Insert into completed_complaints
        con.execute("""
        INSERT INTO completed_complaints
        (id, category, description, full_name, phone, lat, lng, image, created_at,
         completed_at, status_before, processing_time, admin_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
        """, (
            complaint[0], complaint[1], complaint[2], complaint[3], complaint[4],
            complaint[5], complaint[6], complaint[7], complaint[8],
            complaint[9] if len(complaint) > 9 else 'pending', processing_time, admin_notes
        ))
        
        # Delete from complaints
        con.execute("DELETE FROM complaints WHERE id = ?", (complaint_id,))

def get_status_counts(period: Optional[str] = None) -> Dict[str, int]:
    """Get counts of complaints by status"""
    with sqlite3.connect("data.db") as con:
        counts = {}
        params = []
        
        # Base queries
        pending_query = "SELECT COUNT(*) FROM complaints WHERE status = 'pending'"
        processing_query = "SELECT COUNT(*) FROM complaints WHERE status = 'processing'"
        completed_query = "SELECT COUNT(*) FROM completed_complaints"
        
        if period:
            since = _get_time_period(period)
            time_condition = " AND datetime(created_at) > ?" if period != "completed" else " WHERE datetime(completed_at) > ?"
            params.append(since.isoformat())
            
            pending_query += time_condition
            processing_query += time_condition
            completed_query = "SELECT COUNT(*) FROM completed_complaints WHERE datetime(completed_at) > ?"
            
        counts['pending'] = con.execute(pending_query, tuple(params)).fetchone()[0]
        counts['processing'] = con.execute(processing_query, tuple(params)).fetchone()[0]
        counts['completed'] = con.execute(completed_query, tuple(params)).fetchone()[0]
        
        return counts

def get_processing_history(complaint_id: int) -> List[sqlite3.Row]:
    """Get processing history for a specific complaint"""
    with sqlite3.connect("data.db") as con:
        con.row_factory = sqlite3.Row
        return con.execute("""
        SELECT * FROM processing_history
        WHERE complaint_id = ?
        ORDER BY changed_at DESC
        """, (complaint_id,)).fetchall()


# Initialize the database when module is imported
init_db()