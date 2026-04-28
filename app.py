from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime, timedelta
import json
import uuid
import random

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect('bus.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

def calculate_refund(booktime_str, deptime_str):
    deptime = datetime.fromisoformat(deptime_str)
    now = datetime.now()
    diff = deptime - now
    hrs = diff.total_seconds() / 3600
    if hrs > 24:
        return 0.90
    elif 12 < hrs <= 24:
        return 0.75
    elif 6 < hrs <= 12:
        return 0.50
    elif 1 < hrs <= 6:
        return 0.25
    else:
        return 0.0

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

@app.route('/api/search', methods=['GET'])
def search():
    source = request.args.get('source')
    dest = request.args.get('destination')
    date_str = request.args.get('date')
    
    if not source or not dest or not date_str:
        return jsonify({"error": "Missing parameters"}), 400
        
    try:
        search_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    now = datetime.now()
    if search_date.date() < now.date():
        return jsonify({"error": "Cannot travel in past dates."}), 400

    conn = get_db()
    c = conn.cursor()
    
    # Cleanup expired holds
    c.execute("DELETE FROM seathold WHERE expiretime < ?", (now.isoformat(),))
    conn.commit()

    def get_schedules_for_date(target_date):
        start_date = target_date.replace(hour=0, minute=0, second=0)
        end_date = start_date + timedelta(days=1)
        
        c.execute("""
            SELECT s.scheduleid, b.busnumber, b.type, b.totalseats, r.distance, r.duration, 
                   s.departuretime, s.arrivaltime, s.fare
            FROM schedule s
            JOIN bus b ON s.busid = b.busid
            JOIN route r ON s.routeid = r.routeid
            WHERE r.source = ? AND r.destination = ? AND s.departuretime >= ? AND s.departuretime < ?
        """, (source, dest, start_date.isoformat(), end_date.isoformat()))
        return c.fetchall()

    rows = get_schedules_for_date(search_date)
    
    # Check if there are no seats on selected dates (all buses full)
    schedules = []
    ac_available = False
    for r in rows:
        scheduleid = r['scheduleid']
        c.execute("SELECT seats FROM booking WHERE scheduleid = ? AND status='CONFIRMED'", (scheduleid,))
        booked_seats = []
        for b in c.fetchall():
            booked_seats.extend(json.loads(b['seats']))
            
        c.execute("SELECT seats FROM seathold WHERE scheduleid = ?", (scheduleid,))
        for b in c.fetchall():
            booked_seats.extend(json.loads(b['seats']))
            
        avail = r['totalseats'] - len(booked_seats)
        if avail > 0:
            schedules.append({
                "scheduleid": scheduleid,
                "busnumber": r['busnumber'],
                "type": r['type'],
                "duration": r['duration'],
                "departuretime": r['departuretime'],
                "arrivaltime": r['arrivaltime'],
                "fare": r['fare'],
                "available_seats": avail,
                "booked_seats": booked_seats,
                "totalseats": r['totalseats']
            })
            if r['type'] == 'AC':
                ac_available = True

    suggestion_msg = None
    if not schedules:
        # Suggest next available dates
        next_date = search_date + timedelta(days=1)
        next_schedules = get_schedules_for_date(next_date)
        if next_schedules:
            suggestion_msg = f"No seats available on {date_str}. We found buses on {next_date.strftime('%Y-%m-%d')}."
        else:
            suggestion_msg = f"No seats available on {date_str} and next day."

    # If AC not available, offer Non-AC logic
    # In frontend, we can highlight Non-AC if AC was requested, or just show a banner.
    ac_msg = None
    if not ac_available and len(schedules) > 0:
        ac_msg = "AC buses are currently unavailable on this route. Offering Non-AC buses with reduced fares."

    conn.close()
    return jsonify({
        "schedules": schedules,
        "suggestion": suggestion_msg,
        "ac_message": ac_msg
    })

@app.route('/api/hold', methods=['POST'])
def hold_seats():
    data = request.json
    scheduleid = data.get('scheduleid')
    seats = data.get('seats') # list of int
    passengers = data.get('passengers') # list of dict {gender: 'M/F'}
    
    if not scheduleid or not seats:
        return jsonify({"error": "Missing parameters"}), 400
        
    if len(seats) > 6:
        return jsonify({"error": "Only a maximum of 6 seats per booking allowed."}), 400

    # Ladies seat logic (seats 1 and 2 are ladies only)
    ladies_seats = [1, 2]
    for i, seat in enumerate(seats):
        if seat in ladies_seats:
            if i < len(passengers):
                if passengers[i].get('gender') == 'M':
                    return jsonify({"error": f"Seat {seat} is reserved for ladies. Please select a general seat."}), 400

    conn = get_db()
    c = conn.cursor()
    
    now = datetime.now()
    c.execute("DELETE FROM seathold WHERE expiretime < ?", (now.isoformat(),))
    
    # Check if seat already taken
    c.execute("SELECT seats FROM booking WHERE scheduleid = ? AND status='CONFIRMED'", (scheduleid,))
    all_booked = []
    for b in c.fetchall():
        all_booked.extend(json.loads(b['seats']))
        
    c.execute("SELECT seats FROM seathold WHERE scheduleid = ?", (scheduleid,))
    for b in c.fetchall():
        all_booked.extend(json.loads(b['seats']))
        
    for s in seats:
        if s in all_booked:
            conn.close()
            return jsonify({"error": "Seat just got booked and reselect."}), 400
            
    # Create hold
    holdid = str(uuid.uuid4())
    expiretime = now + timedelta(minutes=8)
    c.execute("INSERT INTO seathold (holdid, scheduleid, seats, expiretime) VALUES (?, ?, ?, ?)",
              (holdid, scheduleid, json.dumps(seats), expiretime.isoformat()))
              
    conn.commit()
    conn.close()
    
    return jsonify({"holdid": holdid, "expiretime": expiretime.isoformat()})

@app.route('/api/book', methods=['POST'])
def book():
    data = request.json
    holdid = data.get('holdid')
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT * FROM seathold WHERE holdid = ?", (holdid,))
    hold = c.fetchone()
    
    if not hold:
        conn.close()
        return jsonify({"error": "Hold expired or invalid. Please reselect seats."}), 400
        
    now = datetime.now()
    if datetime.fromisoformat(hold['expiretime']) < now:
        c.execute("DELETE FROM seathold WHERE holdid = ?", (holdid,))
        conn.commit()
        conn.close()
        return jsonify({"error": "Hold time (8 minutes) expired. Please reselect."}), 400
        
    scheduleid = hold['scheduleid']
    seats = json.loads(hold['seats'])
    
    c.execute("SELECT fare FROM schedule WHERE scheduleid = ?", (scheduleid,))
    base_fare = c.fetchone()['fare']
    
    total_fare = base_fare * len(seats)
    if len(seats) > 4:
        total_fare = total_fare * 0.90 # 10% discount
        
    pnr = "PNR" + str(random.randint(100000, 999999))
    c.execute("INSERT INTO booking (pnr, name, phone, email, scheduleid, seats, fare, status, boardingpass, booktime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (pnr, name, phone, email, scheduleid, json.dumps(seats), total_fare, 'CONFIRMED', pnr, now.isoformat()))
              
    c.execute("DELETE FROM seathold WHERE holdid = ?", (holdid,))
    conn.commit()
    conn.close()
    
    return jsonify({"pnr": pnr, "message": "Booking Confirmed", "fare": total_fare})

@app.route('/api/ticket/<pnr>', methods=['GET'])
def get_ticket(pnr):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT b.pnr, b.name, b.phone, b.email, b.seats, b.fare, b.status, b.booktime,
               s.departuretime, s.arrivaltime, r.source, r.destination, bus.busnumber, bus.type
        FROM booking b
        JOIN schedule s ON b.scheduleid = s.scheduleid
        JOIN route r ON s.routeid = r.routeid
        JOIN bus ON s.busid = bus.busid
        WHERE b.pnr = ?
    ''', (pnr,))
    ticket = c.fetchone()
    conn.close()
    
    if not ticket:
        return jsonify({"error": "booking not found error"}), 404
        
    return jsonify(dict(ticket))

@app.route('/api/cancel', methods=['POST'])
def cancel():
    data = request.json
    pnr = data.get('pnr')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT b.pnr, b.status, s.departuretime, b.fare
        FROM booking b
        JOIN schedule s ON b.scheduleid = s.scheduleid
        WHERE b.pnr = ?
    ''', (pnr,))
    ticket = c.fetchone()
    
    if not ticket:
        conn.close()
        return jsonify({"error": "booking not found error"}), 404
        
    if ticket['status'] == 'CANCELLED':
        conn.close()
        return jsonify({"error": "Ticket already cancelled"}), 400
        
    now = datetime.now()
    deptime = datetime.fromisoformat(ticket['departuretime'])
    
    if now > deptime:
        conn.close()
        return jsonify({"error": "Cancellation cannot be done after the bus departure."}), 400
        
    refund_pct = calculate_refund(None, ticket['departuretime'])
    refund_amt = ticket['fare'] * refund_pct
    
    c.execute("UPDATE booking SET status = 'CANCELLED' WHERE pnr = ?", (pnr,))
    conn.commit()
    conn.close()
    
    return jsonify({
        "message": "Ticket cancelled successfully",
        "refund_percentage": f"{refund_pct*100}%",
        "refund_amount": refund_amt
    })

@app.route('/api/board', methods=['POST'])
def board():
    data = request.json
    pnr = data.get('pnr')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status FROM booking WHERE pnr = ?", (pnr,))
    ticket = c.fetchone()
    
    if not ticket:
        conn.close()
        return jsonify({"error": "booking not found error"}), 404
        
    if ticket['status'] != 'CONFIRMED':
        conn.close()
        return jsonify({"error": "Ticket is not confirmed"}), 400
        
    c.execute("UPDATE booking SET status = 'TRAVELLED' WHERE pnr = ?", (pnr,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Passenger boarded successfully. Seats marked as travelled."})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
