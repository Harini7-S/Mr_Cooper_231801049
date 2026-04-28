import sqlite3
from datetime import datetime, timedelta
import json

def init_db():
    conn = sqlite3.connect('bus.db')
    c = conn.cursor()

    # Bus
    c.execute('''CREATE TABLE IF NOT EXISTS bus (
                 busid INTEGER PRIMARY KEY AUTOINCREMENT,
                 busnumber TEXT,
                 type TEXT,
                 totalseats INTEGER
                 )''')

    # Route
    c.execute('''CREATE TABLE IF NOT EXISTS route (
                 routeid INTEGER PRIMARY KEY AUTOINCREMENT,
                 source TEXT,
                 destination TEXT,
                 distance REAL,
                 duration REAL
                 )''')

    # Schedule
    c.execute('''CREATE TABLE IF NOT EXISTS schedule (
                 scheduleid INTEGER PRIMARY KEY AUTOINCREMENT,
                 busid INTEGER,
                 routeid INTEGER,
                 departuretime DATETIME,
                 arrivaltime DATETIME,
                 fare REAL,
                 FOREIGN KEY(busid) REFERENCES bus(busid),
                 FOREIGN KEY(routeid) REFERENCES route(routeid)
                 )''')

    # Booking
    c.execute('''CREATE TABLE IF NOT EXISTS booking (
                 pnr TEXT PRIMARY KEY,
                 name TEXT,
                 phone TEXT,
                 email TEXT,
                 scheduleid INTEGER,
                 seats TEXT,
                 fare REAL,
                 status TEXT,
                 boardingpass TEXT,
                 booktime DATETIME,
                 FOREIGN KEY(scheduleid) REFERENCES schedule(scheduleid)
                 )''')
    
    # Seat Hold
    c.execute('''CREATE TABLE IF NOT EXISTS seathold (
                 holdid TEXT PRIMARY KEY,
                 scheduleid INTEGER,
                 seats TEXT,
                 expiretime DATETIME
                 )''')

    # Insert mock data if empty
    c.execute("SELECT COUNT(*) FROM bus")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO bus (busnumber, type, totalseats) VALUES (?, ?, ?)", [
            ('TN-01-AB-1234', 'AC', 20),
            ('TN-02-CD-5678', 'Non-AC', 20)
        ])
        
        c.executemany("INSERT INTO route (source, destination, distance, duration) VALUES (?, ?, ?, ?)", [
            ('Chennai', 'Bangalore', 350.0, 6.5)
        ])

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(10): 
            d_date = today + timedelta(days=i)
            dep1 = d_date + timedelta(hours=22, minutes=0)
            arr1 = dep1 + timedelta(hours=6, minutes=30)
            c.execute("INSERT INTO schedule (busid, routeid, departuretime, arrivaltime, fare) VALUES (?, ?, ?, ?, ?)", (1, 1, dep1, arr1, 800.0))
            
            dep2 = d_date + timedelta(hours=23, minutes=0)
            arr2 = dep2 + timedelta(hours=6, minutes=30)
            c.execute("INSERT INTO schedule (busid, routeid, departuretime, arrivaltime, fare) VALUES (?, ?, ?, ?, ?)", (2, 1, dep2, arr2, 500.0))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
