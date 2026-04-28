let state = {
    schedules: [],
    selectedSchedule: null,
    selectedSeats: [],
    holdId: null,
    holdInterval: null,
    passengers: [] // array of { gender: 'M'|'F' }
};

// Utilities
function showSection(id) {
    document.querySelectorAll('.view-section').forEach(sec => {
        sec.classList.remove('active');
        sec.classList.add('hidden');
    });
    const section = document.getElementById(id);
    section.classList.remove('hidden');
    section.classList.add('active');
}

function showMessage(containerId, message, type = 'info') {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="message-box ${type}">${message}</div>`;
}

function clearMessages(containerId) {
    document.getElementById(containerId).innerHTML = '';
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    // Set min date for journey to today
    const dateInput = document.getElementById('journey-date');
    const today = new Date().toISOString().split('T')[0];
    dateInput.setAttribute('min', today);
    dateInput.value = today;

    // Fetch locations
    fetch('/api/locations')
        .then(res => res.json())
        .then(data => {
            const sourceSelect = document.getElementById('source');
            const destSelect = document.getElementById('destination');
            data.sources.forEach(loc => sourceSelect.innerHTML += `<option value="${loc}">${loc}</option>`);
            data.destinations.forEach(loc => destSelect.innerHTML += `<option value="${loc}">${loc}</option>`);
        });

    // Form listeners
    document.getElementById('search-form').addEventListener('submit', handleSearch);
    document.getElementById('proceed-seats-btn').addEventListener('click', proceedToDetails);
    document.getElementById('booking-form').addEventListener('submit', handleBooking);
    document.getElementById('pnr-form').addEventListener('submit', handleManageTicket);
    document.getElementById('cancel-ticket-btn').addEventListener('click', handleCancelTicket);
});

// Search functionality
async function handleSearch(e) {
    e.preventDefault();
    const source = document.getElementById('source').value;
    const dest = document.getElementById('destination').value;
    const date = document.getElementById('journey-date').value;

    if (source === dest) {
        alert("Source and destination cannot be the same.");
        return;
    }

    try {
        const res = await fetch(`/api/search?source=${source}&destination=${dest}&date=${date}`);
        const data = await res.json();
        
        if (!res.ok) {
            alert(data.error);
            return;
        }

        document.getElementById('search-info').innerText = `${source} to ${dest} on ${date}`;
        clearMessages('messages-container');
        
        if (data.suggestion) {
            showMessage('messages-container', data.suggestion, 'info');
        }
        if (data.ac_message) {
            showMessage('messages-container', data.ac_message, 'info');
        }

        renderBusList(data.schedules);
        showSection('bus-list-section');
    } catch (err) {
        console.error(err);
        alert("An error occurred while searching.");
    }
}

function renderBusList(schedules) {
    const container = document.getElementById('bus-list');
    container.innerHTML = '';
    
    if (schedules.length === 0) {
        container.innerHTML = '<p>No buses found for this route.</p>';
        return;
    }

    schedules.forEach(bus => {
        const dep = new Date(bus.departuretime).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const arr = new Date(bus.arrivaltime).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const acClass = bus.type === 'AC' ? 'ac' : 'non-ac';

        const card = document.createElement('div');
        card.className = 'bus-card';
        card.innerHTML = `
            <div class="bus-info">
                <h3>${bus.busnumber} <span class="badge ${acClass}">${bus.type}</span></h3>
                <div class="bus-timing">
                    <span><strong>Dep:</strong> ${dep}</span>
                    <span><strong>Arr:</strong> ${arr}</span>
                    <span><strong>Duration:</strong> ${bus.duration} hrs</span>
                </div>
                <p style="margin-top: 0.5rem; color: var(--text-muted); font-size: 0.9rem;">
                    Seats Available: ${bus.available_seats}/${bus.totalseats}
                </p>
            </div>
            <div class="bus-action">
                <div class="bus-fare">₹${bus.fare}</div>
                <button class="btn primary-btn" onclick='openSeatMap(${JSON.stringify(bus)})'>Select Seats</button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Seat Selection functionality
function openSeatMap(busStr) {
    const bus = typeof busStr === 'string' ? JSON.parse(busStr) : busStr;
    state.selectedSchedule = bus;
    state.selectedSeats = [];
    
    const grid = document.getElementById('seat-grid');
    grid.innerHTML = '';
    
    // Generate seats (assuming 40 total, 10 rows of 4)
    for (let i = 1; i <= bus.totalseats; i++) {
        const seat = document.createElement('div');
        seat.className = 'seat';
        seat.innerText = i;
        
        if (bus.booked_seats.includes(i)) {
            seat.classList.add('booked');
        } else if (i === 1 || i === 2) {
            seat.classList.add('ladies');
        } else {
            seat.classList.add('general');
        }

        seat.onclick = () => toggleSeat(i, seat);
        grid.appendChild(seat);
    }
    
    updateSeatSummary();
    showSection('seat-selection-section');
}

function toggleSeat(seatNo, seatElem) {
    if (seatElem.classList.contains('booked')) return;
    
    const index = state.selectedSeats.indexOf(seatNo);
    if (index > -1) {
        state.selectedSeats.splice(index, 1);
        seatElem.classList.remove('selected');
    } else {
        if (state.selectedSeats.length >= 6) {
            alert("Only a maximum of 6 seats per booking allowed.");
            return;
        }
        state.selectedSeats.push(seatNo);
        seatElem.classList.add('selected');
    }
    updateSeatSummary();
}

function updateSeatSummary() {
    const textElem = document.getElementById('selected-seats-text');
    const btn = document.getElementById('proceed-seats-btn');
    
    if (state.selectedSeats.length > 0) {
        textElem.innerText = state.selectedSeats.join(', ');
        btn.disabled = false;
    } else {
        textElem.innerText = 'None';
        btn.disabled = true;
    }
}

// Details & Hold Functionality
async function proceedToDetails() {
    // Generate Gender inputs for ladies seats check
    const ladiesSeats = state.selectedSeats.filter(s => s === 1 || s === 2);
    const container = document.getElementById('passenger-genders-container');
    container.innerHTML = '';
    
    state.passengers = [];
    
    if (ladiesSeats.length > 0) {
        container.innerHTML = '<p class="subtitle" style="margin-bottom:1rem; font-size:0.9rem;">You have selected Ladies Only seats. Please confirm passenger genders.</p>';
        state.selectedSeats.forEach((seat, idx) => {
            const isLadies = seat === 1 || seat === 2;
            const div = document.createElement('div');
            div.className = 'input-group';
            div.style.marginBottom = '1rem';
            div.innerHTML = `
                <label>Passenger ${idx + 1} (Seat ${seat})</label>
                <select id="gender-${idx}" required>
                    <option value="" disabled selected>Select Gender</option>
                    ${isLadies ? '<option value="F">Female</option>' : '<option value="M">Male</option><option value="F">Female</option>'}
                </select>
            `;
            container.appendChild(div);
        });
    } else {
        container.innerHTML = '<p class="subtitle" style="margin-bottom:1rem; font-size:0.9rem;">No ladies only seats selected. General booking applies.</p>';
    }

    // Attempt to hold seats
    // But since we need genders to hold (to validate ladies seats on backend), 
    // wait, if ladies seats selected, we might need gender first. 
    // The requirement says "if male passenger requests ladies-only seats then block and suggest general seats."
    // Let's ask for details AND hold simultaneously, or hold first?
    // The backend API requires passengers array. Let's do a dummy hold if no ladies seats, 
    // else we have to prompt genders FIRST before holding.
    
    // To simplify: we show the form, user fills it. Hold is created ONLY when they click "Pay".
    // Wait, requirement: "The system holds seat for 8 minutes and The passenger enters details."
    // So hold first. If a male tries to hold ladies seat without gender? We can't validate yet.
    // Let's validate on frontend first for hold: "if male requests ladies..."
    // Since we don't know gender until they fill the form, let's just hold them blindly, 
    // and if they submit male gender for ladies seat, we error out at booking.
    // Actually, backend hold API takes `passengers` to validate. Let's pass empty and let backend allow it if we don't send genders yet.
    
    try {
        const res = await fetch('/api/hold', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                scheduleid: state.selectedSchedule.scheduleid,
                seats: state.selectedSeats,
                passengers: [] // Send empty, backend only errors if gender is 'M'
            })
        });
        
        const data = await res.json();
        if (!res.ok) {
            alert(data.error);
            // "if the seat is already taken - error: seat just got booked and reselect."
            showSection('bus-list-section'); // Go back
            return;
        }
        
        state.holdId = data.holdid;
        startTimer(new Date(data.expiretime));
        
        // Update Fare Summary
        let baseFare = state.selectedSchedule.fare;
        let count = state.selectedSeats.length;
        let total = baseFare * count;
        let discountMsg = '';
        if (count > 4) {
            total = total * 0.90;
            discountMsg = '<br><span style="color:var(--success); font-size:0.9rem;">10% Group Discount Applied!</span>';
        }
        
        document.getElementById('fare-breakdown').innerHTML = `
            ${count} x ₹${baseFare} = ₹${baseFare * count}
            ${discountMsg}
            <br><strong style="font-size:1.2rem; margin-top:0.5rem; display:block;">Total: ₹${total}</strong>
        `;

        showSection('passenger-details-section');
    } catch (err) {
        console.error(err);
        alert("Error holding seats.");
    }
}

function startTimer(expireTime) {
    if (state.holdInterval) clearInterval(state.holdInterval);
    
    const display = document.getElementById('hold-timer');
    
    state.holdInterval = setInterval(() => {
        const now = new Date();
        const diff = expireTime - now;
        
        if (diff <= 0) {
            clearInterval(state.holdInterval);
            display.innerText = "00:00";
            alert("Hold time expired. Please reselect seats.");
            showSection('bus-list-section');
            return;
        }
        
        const m = Math.floor((diff / 1000 / 60) % 60);
        const s = Math.floor((diff / 1000) % 60);
        display.innerText = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }, 1000);
}

// Booking
async function handleBooking(e) {
    e.preventDefault();
    
    // Check ladies seats frontend validation
    const ladiesSeats = state.selectedSeats.filter(s => s === 1 || s === 2);
    if (ladiesSeats.length > 0) {
        for (let i = 0; i < state.selectedSeats.length; i++) {
            const seat = state.selectedSeats[i];
            const genderSelect = document.getElementById(`gender-${i}`);
            if (genderSelect) {
                const gender = genderSelect.value;
                if ((seat === 1 || seat === 2) && gender === 'M') {
                    alert(`Seat ${seat} is reserved for ladies. Please go back and select a general seat.`);
                    return;
                }
            }
        }
    }

    const name = document.getElementById('contact-name').value;
    const phone = document.getElementById('contact-phone').value;
    const email = document.getElementById('contact-email').value;

    try {
        const res = await fetch('/api/book', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                holdid: state.holdId,
                name, phone, email
            })
        });
        
        const data = await res.json();
        if (!res.ok) {
            alert(data.error);
            if (data.error.includes('expired')) {
                showSection('bus-list-section');
            }
            return;
        }
        
        clearInterval(state.holdInterval);
        
        // Show Ticket
        fetchTicketAndShow(data.pnr);

    } catch (err) {
        console.error(err);
        alert("Error confirming booking.");
    }
}

async function fetchTicketAndShow(pnr) {
    try {
        const res = await fetch(`/api/ticket/${pnr}`);
        const ticket = await res.json();
        
        if (!res.ok) {
            alert(ticket.error);
            return;
        }
        
        renderTicket(ticket);
        showSection('ticket-section');
        
    } catch (err) {
        console.error(err);
    }
}

function renderTicket(ticket) {
    document.getElementById('ticket-pnr').innerText = ticket.pnr;
    document.getElementById('ticket-name').innerText = ticket.name;
    document.getElementById('ticket-source').innerText = ticket.source;
    document.getElementById('ticket-dest').innerText = ticket.destination;
    
    const dep = new Date(ticket.departuretime).toLocaleString([], {month:'short', day:'numeric', hour: '2-digit', minute:'2-digit'});
    const arr = new Date(ticket.arrivaltime).toLocaleString([], {month:'short', day:'numeric', hour: '2-digit', minute:'2-digit'});
    
    document.getElementById('ticket-deptime').innerText = dep;
    document.getElementById('ticket-arrtime').innerText = arr;
    
    document.getElementById('ticket-bus').innerText = `${ticket.busnumber} (${ticket.type})`;
    document.getElementById('ticket-seats').innerText = JSON.parse(ticket.seats).join(', ');
    document.getElementById('ticket-fare').innerText = `₹${ticket.fare}`;
    
    const badge = document.getElementById('ticket-status');
    badge.innerText = ticket.status;
    if (ticket.status === 'CANCELLED') {
        badge.style.color = '#fca5a5';
        badge.style.background = 'rgba(239, 68, 68, 0.2)';
    } else {
        badge.style.color = '#34d399';
        badge.style.background = 'rgba(16, 185, 129, 0.2)';
    }
}

// Manage / Cancel Ticket
async function handleManageTicket(e) {
    e.preventDefault();
    const pnr = document.getElementById('search-pnr').value;
    document.getElementById('cancel-msg').innerText = '';
    
    try {
        const res = await fetch(`/api/ticket/${pnr}`);
        const ticket = await res.json();
        
        if (!res.ok) {
            alert(ticket.error); // "booking not found error"
            return;
        }
        
        // Render minimal ticket info
        const container = document.getElementById('manage-ticket-container');
        container.innerHTML = `
            <div style="background: rgba(0,0,0,0.2); padding: 1.5rem; border-radius: 10px; margin-bottom: 1.5rem;">
                <p><strong>PNR:</strong> ${ticket.pnr}</p>
                <p><strong>Name:</strong> ${ticket.name}</p>
                <p><strong>Journey:</strong> ${ticket.source} to ${ticket.destination}</p>
                <p><strong>Status:</strong> <span style="color: ${ticket.status==='CANCELLED'?'#fca5a5':'#34d399'}">${ticket.status}</span></p>
            </div>
        `;
        
        document.getElementById('manage-ticket-result').classList.remove('hidden');
        
        const cancelBtn = document.getElementById('cancel-ticket-btn');
        if (ticket.status === 'CANCELLED') {
            cancelBtn.style.display = 'none';
        } else {
            cancelBtn.style.display = 'block';
            cancelBtn.onclick = () => doCancelTicket(ticket.pnr);
        }
        
    } catch (err) {
        console.error(err);
    }
}

async function doCancelTicket(pnr) {
    if (!confirm('Are you sure you want to cancel this ticket? Cancellation charges will apply.')) return;
    
    try {
        const res = await fetch('/api/cancel', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ pnr })
        });
        
        const data = await res.json();
        if (!res.ok) {
            alert(data.error);
            return;
        }
        
        document.getElementById('cancel-msg').innerText = `Successfully cancelled. Refund: ₹${data.refund_amount} (${data.refund_percentage})`;
        document.getElementById('cancel-ticket-btn').style.display = 'none';
        
    } catch(err) {
        console.error(err);
        alert("Error cancelling ticket");
    }
}
