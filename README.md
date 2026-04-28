# Mr_Cooper_231801049 - Long code round
						            BUS RESERVATION SYSTEM - UC -013
Problem Statement:

I am going to design a bus reservation system that is easily accessible by the users.

The system has 3 main users they are, 
		-->Passenger
		-->Bus Operator(Admin)
		-->System(Schedule Manager)


Approach & Logic used:

Tech Stacks used :

Frontend --
	*html
	*Inline CSS
	*java script

Backend --
	*Python
	*Flask

Database --
	*SQLite3


Flow :

Passenger --
 1. The passenger searches for a ticket in a specific date from a source to destination.
 2. The Available buses with fare, duration(start time, end time, hours of travel) and seat availability is displayed.
	*if there is no seat on selected dates then the system suggests dates with availability.
	*Cannot travel in the past dates, don't show past dates.
 3. Passenger selects a bus and preferred seats.
 4. The system holds seat for 8 minutes and The passenger enters details.
	*if male passengers requests ladies-only seats then block and suggest general seats.
	*Apply 10% discount for group booking more than 4 seats.
	*if AC bus is not available then offer Non-AC with reduced fare.
 5. The passenger pays, then booking confirmed, boarding pass generated with PNR.
	*if the seat is already taken - error: seat just got booked and reselect.
	*Only a maximum of 6 seats per booking.
 6. Passengers can check their booked tickets in the portal whenever needed and cancellation can be done with some charges.
	*if the PNR is invalid - booking not found error.
 7. On the day of travel passenger boards with PNR, System marks seats as travelled.
 	*Cancellation cannot be done after the bus departure.

Admin (Bus operator) --

1. Checks each passenger and marks them travelled.

System Admin (Bus Scheduler) --

1. System admin can add buses.


 
Tables used:

Bus - busid, busnumber, type, seatmap[][] --getseatMap(), get availableseats(), assignseats()

Route - routeid,source, destination, stops[], distance(Km), duration(hrs)  --getFare(),getSchedules()

Schedule - scheduleid, busid, routeid, departuretime, arrivaltime, fare --getavailability(), hold() , isexpired()

Booking - pnr, passengerid, scheduleid, seats[], fare, status, boardingpass --confirm(), cancel(), generate boardingpass()

Passenger - passengerid, name, phone , email, idproof --searchbus(), bookticket(),cancelticket()

Cancelpolicy - hoursbeforedeparture, refund percent -- calculaterefund(hrsremaining)


Refund policy:

>24 hrs - 90% refund
12-24 hrs - 75% refundz
6-12 hrs - 50% refund
1-6 hrs -  25% refund
<1 hr   - no refund


How to run the code :
	
	*directly run -- bus_reservation.py (since we already have bus.db)
		code:
			python bus_reservation.py

	*else run database.py and then bus_reservation.py(Optional)
		code:
			python database.py
			python bus_reservation.py
