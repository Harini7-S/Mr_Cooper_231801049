from flask import Flask, request, jsonify, send_from_directory
import sqlite3
from datetime import datetime, timedelta
import json
import uuid
import random
import os

app = Flask(__name__)

#database connection

def get_db():
    conn = sqlite3.connect('bus.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

#refund calculation based on hours before departure
def calculate_refund(deptime_str):
    deptime = datetime.fromisoformat(deptime_str)
    now = datetime.now()
    diff = deptime - now
    hrs = diff.total_seconds() / 3600
    if hrs > 24: return 0.90
    elif 12 < hrs <= 24: return 0.75
    elif 6 < hrs <= 12: return 0.50
    elif 1 < hrs <= 6: return 0.25
    return 0.0

#API endpoints
@app.route('/api/locations', methods=['GET'])
def get_locations():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT source FROM route")
    sources = [r[0] for r in c.fetchall()]
    c.execute("SELECT DISTINCT destination FROM route")
    dests = [r[0] for r in c.fetchall()]
    conn.close()
    return jsonify({"sources": sources, "destinations": dests})

#search
@app.route('/api/search', methods=['GET'])
def search():
    source = request.args.get('source')
    dest = request.args.get('destination')
    date_str = request.args.get('date')
    
    try:
        search_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    now = datetime.now()
    if search_date.date() < now.date():
        return jsonify({"error": "Cannot travel in past dates."}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM seathold WHERE expiretime < ?", (now.isoformat(),))
    conn.commit()
#get schedules for the day
    def get_schedules(target_date):
        start = target_date.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)
        c.execute("""
            SELECT s.scheduleid, b.busnumber, b.type, b.totalseats, r.duration, s.departuretime, s.fare
            FROM schedule s
            JOIN bus b ON s.busid = b.busid
            JOIN route r ON s.routeid = r.routeid
            WHERE r.source = ? AND r.destination = ? AND s.departuretime >= ? AND s.departuretime < ?
        """, (source, dest, start.isoformat(), end.isoformat()))
        return c.fetchall()

    rows = get_schedules(search_date)
    schedules = []
    ac_avail = False
    
    for r in rows:
        c.execute("SELECT seats FROM booking WHERE scheduleid = ? AND status='CONFIRMED'", (r['scheduleid'],))
        booked = []
        for b in c.fetchall(): booked.extend(json.loads(b['seats']))
        c.execute("SELECT seats FROM seathold WHERE scheduleid = ?", (r['scheduleid'],))
        for h in c.fetchall(): booked.extend(json.loads(h['seats']))
            
        avail = r['totalseats'] - len(booked)
        if avail > 0:
            schedules.append({
                "scheduleid": r['scheduleid'],
                "busnumber": r['busnumber'],
                "type": r['type'],
                "duration": r['duration'],
                "fare": r['fare'],
                "totalseats": r['totalseats'],
                "available_seats": avail,
                "booked_seats": booked
            })
            if r['type'] == 'AC': ac_avail = True

    suggestion, ac_msg = None, None
    if not schedules:
        next_d = search_date + timedelta(days=1)
        if get_schedules(next_d):
            suggestion = f"No seats available on {date_str}. Try {next_d.strftime('%Y-%m-%d')}."
        else:
            suggestion = "No seats available."
    elif not ac_avail:
        ac_msg = "AC buses unavailable. Offering Non-AC buses with reduced fares."

    conn.close()
    return jsonify({"schedules": schedules, "suggestion": suggestion, "ac_message": ac_msg})

#seats hold and booking
@app.route('/api/hold', methods=['POST'])
def hold_seats():
    data = request.json
    scheduleid = data.get('scheduleid')
    seats = data.get('seats')
    
    if len(seats) > 6:
        return jsonify({"error": "Max 6 seats allowed."}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM seathold WHERE expiretime < ?", (datetime.now().isoformat(),))
    
    all_booked = []
    c.execute("SELECT seats FROM booking WHERE scheduleid = ? AND status='CONFIRMED'", (scheduleid,))
    for b in c.fetchall(): all_booked.extend(json.loads(b['seats']))
    c.execute("SELECT seats FROM seathold WHERE scheduleid = ?", (scheduleid,))
    for h in c.fetchall(): all_booked.extend(json.loads(h['seats']))
        
    for s in seats:
        if s in all_booked:
            conn.close()
            return jsonify({"error": "Seat just got booked and reselect."}), 400
            
    holdid = str(uuid.uuid4())
    expiretime = datetime.now() + timedelta(minutes=8)
    c.execute("INSERT INTO seathold (holdid, scheduleid, seats, expiretime) VALUES (?, ?, ?, ?)",
              (holdid, scheduleid, json.dumps(seats), expiretime.isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"holdid": holdid, "expiretime": expiretime.isoformat()})

#booking and pnr generation
@app.route('/api/book', methods=['POST'])
def book():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM seathold WHERE holdid = ?", (data['holdid'],))
    hold = c.fetchone()
    
    if not hold or datetime.fromisoformat(hold['expiretime']) < datetime.now():
        conn.close()
        return jsonify({"error": "Hold expired. Reselect seats."}), 400
        
    seats = json.loads(hold['seats'])
    c.execute("SELECT fare FROM schedule WHERE scheduleid = ?", (hold['scheduleid'],))
    fare = c.fetchone()['fare'] * len(seats)
    if len(seats) > 4: fare *= 0.90
        
    pnr = "PNR" + str(random.randint(10000, 99999))
    c.execute("INSERT INTO booking (pnr, name, phone, email, scheduleid, seats, fare, status, boardingpass, booktime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (pnr, data['name'], data['phone'], data['email'], hold['scheduleid'], json.dumps(seats), fare, 'CONFIRMED', pnr, datetime.now().isoformat()))
              
    c.execute("DELETE FROM seathold WHERE holdid = ?", (data['holdid'],))
    conn.commit()
    conn.close()
    return jsonify({"pnr": pnr})
#view ticket
@app.route('/api/ticket/<pnr>', methods=['GET'])
def get_ticket(pnr):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT b.pnr, b.name, b.seats, b.fare, b.status, r.source, r.destination, bus.busnumber, bus.type
        FROM booking b
        JOIN schedule s ON b.scheduleid = s.scheduleid
        JOIN route r ON s.routeid = r.routeid
        JOIN bus ON s.busid = bus.busid
        WHERE b.pnr = ?
    ''', (pnr,))
    ticket = c.fetchone()
    conn.close()
    if not ticket: return jsonify({"error": "booking not found error"}), 404
    return jsonify(dict(ticket))

#cancellation - passenger
@app.route('/api/cancel', methods=['POST'])
def cancel():
    pnr = request.json.get('pnr')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT b.status, s.departuretime, b.fare FROM booking b JOIN schedule s ON b.scheduleid = s.scheduleid WHERE b.pnr = ?", (pnr,))
    ticket = c.fetchone()
    
    if not ticket: return jsonify({"error": "booking not found"}), 404
    if ticket['status'] == 'CANCELLED': return jsonify({"error": "Already cancelled"}), 400
    if datetime.now() > datetime.fromisoformat(ticket['departuretime']):
        return jsonify({"error": "Cannot cancel after departure"}), 400
        
    pct = calculate_refund(ticket['departuretime'])
    c.execute("UPDATE booking SET status = 'CANCELLED' WHERE pnr = ?", (pnr,))
    conn.commit()
    conn.close()
    return jsonify({"refund_percentage": f"{pct*100}%", "refund_amount": ticket['fare'] * pct})
#boarding - bus operator
@app.route('/api/admin/board', methods=['POST'])
def board():
    pnr = request.json.get('pnr')
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE booking SET status = 'TRAVELLED' WHERE pnr = ? AND status = 'CONFIRMED'", (pnr,))
    if c.rowcount == 0:
        conn.close()
        return jsonify({"error": "Invalid PNR or not confirmed."}), 400
    conn.commit()
    conn.close()
    return jsonify({"message": f"PNR {pnr} marked as TRAVELLED."})
#adding bus - bus scheduer
@app.route('/api/admin/addbus', methods=['POST'])
def addbus():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO bus (busnumber, type, totalseats) VALUES (?, ?, ?)",
              (data['busnumber'], data['type'], data['totalseats']))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Bus {data['busnumber']} added successfully."})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
