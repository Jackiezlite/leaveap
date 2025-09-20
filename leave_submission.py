"""
Leave submission backend logic
"""
from datetime import datetime
import sqlite3
import os
import configparser
from pathlib import Path
import xlwings as xw

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

DB_PATH = config['database']['path']
TEMPLATE_PATH = config['files']['template_path']
OUTPUT_PATH = config['files']['output_path']

def submit_leave_request(user_id: int, leave_type: str, start_date: str, 
                        num_days: float, notes: str = None, 
                        attachment: bytes = None) -> int:
    """Submit a new leave request and handle Excel form generation"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Check leave balance
        c.execute("""
            SELECT TotalLeave, SickLeave, cultivationLeave,
                   compassionateLeave, hospital_leave,
                   ReplacementLeave, pregnantLeave
            FROM Users WHERE id = ?
        """, (user_id,))
        balances = dict(zip(
            ['TotalLeave', 'SickLeave', 'cultivationLeave',
             'compassionateLeave', 'hospital_leave',
             'ReplacementLeave', 'pregnantLeave'],
            c.fetchone()
        ))
        
        # Get user details
        c.execute("SELECT username FROM Users WHERE id = ?", (user_id,))
        username = c.fetchone()[0]
        
        # Validate leave balance
        leave_type_mapping = {
            'Annual Leave': 'TotalLeave',
            'Sick Leave': 'SickLeave',
            'Cultivation Leave': 'cultivationLeave',
            'Compassionate Leave': 'compassionateLeave',
            'Hospital Leave': 'hospital_leave',
            'Working on Off/PH': 'ReplacementLeave',
            'Maternity Leave': 'pregnantLeave'
        }
        
        balance_type = leave_type_mapping.get(leave_type)
        if balance_type and balances[balance_type] < num_days:
            raise ValueError(f"Insufficient {leave_type} balance")
        
        # Insert leave request
        c.execute("""
            INSERT INTO LeaveRequests 
            (user_id, leave_type, start_date, num_days, notes, attachment_image)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, leave_type, start_date, num_days, notes, attachment))
        leave_id = c.lastrowid
        
        # Log action
        c.execute("""
            INSERT INTO AuditLog 
            (action, performed_by, target_user, change_summary)
            VALUES (?, ?, ?, ?)
        """, (
            'Submit Leave Request',
            str(user_id),
            user_id,
            f"New {leave_type} request for {num_days} days"
        ))
        
        conn.commit()
        
        # Generate Excel form if template exists
        if os.path.exists(TEMPLATE_PATH):
            try:
                fill_excel_form(
                    template_path=TEMPLATE_PATH,
                    output_path=os.path.join(OUTPUT_PATH, f'leave_request_{leave_id}.xlsx'),
                    data={
                        'username': username,
                        'leave_type': leave_type,
                        'start_date': start_date,
                        'num_days': num_days,
                        'notes': notes or ''
                    }
                )
            except Exception as e:
                print(f"Warning: Could not generate Excel form: {e}")
        
        return leave_id

def fill_excel_form(template_path: str, output_path: str, data: dict):
    """Fill Excel leave form template with request data"""
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Copy template to output location
    if not os.path.exists(output_path):
        import shutil
        shutil.copy2(template_path, output_path)
    
    # Fill form using xlwings
    try:
        with xw.App(visible=False) as app:
            wb = app.books.open(output_path)
            sheet = wb.sheets[0]
            
            # Map data to Excel cells (adjust cell references as needed)
            mappings = {
                'username': 'B2',
                'leave_type': 'B3',
                'start_date': 'B4',
                'num_days': 'B5',
                'notes': 'B6'
            }
            
            # Fill data
            for field, cell in mappings.items():
                if field in data:
                    sheet.range(cell).value = data[field]
            
            # Save and close
            wb.save()
            wb.close()
    except Exception as e:
        raise Exception(f"Error filling Excel form: {e}")

def get_leave_balance(user_id: int, leave_type: str) -> float:
    """Get current balance for a specific leave type"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        balance_column = {
            'Annual Leave': 'TotalLeave',
            'Sick Leave': 'SickLeave',
            'Cultivation Leave': 'cultivationLeave',
            'Compassionate Leave': 'compassionateLeave',
            'Hospital Leave': 'hospital_leave',
            'Working on Off/PH': 'ReplacementLeave',
            'Maternity Leave': 'pregnantLeave'
        }.get(leave_type)
        
        if not balance_column:
            raise ValueError(f"Unknown leave type: {leave_type}")
            
        c.execute(f"SELECT {balance_column} FROM Users WHERE id = ?", 
                 (user_id,))
        result = c.fetchone()
        return result[0] if result else 0.0

def get_all_leave_balances(user_id: int) -> dict:
    """Get all leave balances for a user"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT TotalLeave, SickLeave, cultivationLeave,
                   compassionateLeave, hospital_leave,
                   ReplacementLeave, pregnantLeave
            FROM Users WHERE id = ?
        """, (user_id,))
        row = c.fetchone()
        
        if not row:
            return {}
            
        return {
            'Annual Leave': row[0],
            'Sick Leave': row[1],
            'Cultivation Leave': row[2],
            'Compassionate Leave': row[3],
            'Hospital Leave': row[4],
            'Working on Off/PH': row[5],
            'Maternity Leave': row[6]
        }
