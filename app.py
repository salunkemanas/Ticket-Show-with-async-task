from flask import Flask, request, jsonify,render_template, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import json
from celery_worker import make_celery
from celery.result import AsyncResult
from celery.schedules import crontab
from httplib2 import Http
import time
import smtplib
from datetime import *
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from time import *
from jinja2 import Template
from flask_caching import Cache
from sqlalchemy.sql import func


SMPTP_SERVER_HOST = "localhost"
SMPTP_SERVER_PORT = 1025
SENDER_ADDRESS = "21f1002150@ds.study.iitm.ac.in"
SENDER_PASSWORD = ""

SMPTP_SERVER_HOST = "localhost"
SMPTP_SERVER_PORT = 1025
SENDER_ADDRESS = "21f1002150@ds.study.iitm.ac.in"
SENDER_PASSWORD = ""

def send_email(to_address, subject, message, content='text', attachment_file=None):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = SENDER_ADDRESS
    msg['To'] = to_address
    msg.attach(MIMEText(message, "html"))

    s = smtplib.SMTP(host="localhost", port=1025)

    s.login("xyz@gmail.com", "password")
    s.send_message(msg)
    s.quit()
    return True

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///test.sqlite3"
app.config['JWT_SECRET_KEY'] = 'super-secret' 
db = SQLAlchemy(app)
jwt = JWTManager(app)
cache = Cache(app)
app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379',
    REDIS_URL = "redis://localhost:6379",
    CACHE_TYPE = "RedisCache",
    CACHE_REDIS_HOST = "localhost",
    CACHE_REDIS_PORT = 6379
)
celery = make_celery(app)

@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # comment this out
    sender.add_periodic_task(30.0, send_reminder_via_email.s(), name='Daily reminder')
    sender.add_periodic_task(30.0, send_monthly_via_email.s(), name='Monthly report')

    # # Calls send_reminder_via_email every day at 8:30 pm
    # sender.add_periodic_task(crontab(hour=20, minute=30),send_reminder_via_email.s(),)
    # sender.add_periodic_task(crontab(hour=12, minute=0, day_of_month=1),send_monthly_via_email.s(),)


@celery.task()
def send_reminder_via_email():
    interval = datetime.utcnow() - timedelta(days=1)
    users = User.query.filter(~User.shows.any(Association.timestamp >= interval)).all()
    print(users)
    for user in users:
        if user.username == 'admin':
            continue
        send_email(
        to_address=user.username,
        subject="Website Visit",
        message="We have noticed that you have no visited the website or booked tickets for a while now, please pay a visit "
    )
    return "Email should arrive in your inbox shortly"

@celery.task()
def send_monthly_via_email():
    now = datetime.now()
    year = now.year
    month = now.month
    if month == 1:
        month = 12
        year -= 1
    else:
        month -= 1
    users = User.query.all()
    print("Sending Reports")
    done = "Report have been Sent"
    for user in users:
        print(user)
        bookings = Association.query.filter(Association.user_id == user.id, db.extract('year', Association.timestamp) == year, db.extract('month', Association.timestamp) == month).all()
        print(bookings)
        if not bookings:
            continue
        report = f"<h1>Monthly Booking Report for {month}/{year}</h1>"
        report += "<table style='border:2px solid grey; '>"
        report += "<tr><th style='border:2px solid grey; '>Show</th><th style='border:2px solid grey; '>Venue</th><th style='border:2px solid grey; '>Tickets Booked</th></tr>"
        for booking in bookings:
            show = Show.query.get(booking.show_id)
            venue = Venue.query.get(show.venue_id)
            report += f"<tr><td style='border:2px solid grey; '>{show.name}</td><td style='border:2px solid grey; '>{venue.name}</td><td style='border:2px solid grey; '>{booking.tickets}</td></tr>"
        report += "</table>"
        sender='21f1002150@ds.study.iitm.ac.in'
        send_email(
        to_address=user.username,
        subject="Monthly Entertment Report",
        message=report )
        print("sending...")
    print("Reports Sent")
    return  done


@celery.task
def generate_csv(id):
    import csv
    # time.sleep(6)
    fields = ['ShowName', 'Rating', 'Timing', 'Ticket price', 'Tags', 'VenueName']
    rows = get_rows(id)
    with open("static/data.csv", 'w') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(fields)
        csvwriter.writerows(rows)

    return "Job Started..."

def get_rows(id):
    venue = Venue.query.filter_by(id=id).first()
    row = []
    for show in venue.shows:
        row.append([show.name, show.rating, show.timing, show.ticket_price, show.tags, venue.name ])
    return row


@celery.task
def send_reminder():
    url = "https://chat.googleapis.com/v1/spaces/AAAAWHWxhoE/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=9L2YwDmKdHqI8-HFNV6NFtZxzPlOxGU6LRdF3Olis58"
    app_message = {
        'text': 'Hello from a Python script!'}
    message_headers = {'Content-Type': 'application/json; charset=UTF-8'}
    http_obj = Http()
    response = http_obj.request(
        uri=url,
        method='POST',
        headers=message_headers,
        body=json.dumps(app_message),
    )
    print(response)


class Venue(db.Model):
    id = db.Column(db.Integer(), primary_key = True)
    name = db.Column(db.String())
    place = db.Column(db.String())
    location = db.Column(db.String())
    capacity = db.Column(db.Integer())
    shows = db.relationship('Show', backref="venue", lazy="subquery")

class Show(db.Model):
    id = db.Column(db.Integer(), primary_key = True)
    name = db.Column(db.String())
    rating = db.Column(db.Integer())
    timing = db.Column(db.String()) 
    ticket_price = db.Column(db.Integer())
    tags = db.Column(db.String())
    venue_id = db.Column(db.Integer(), db.ForeignKey("venue.id"))
    bookings = db.relationship('User', backref="shows", secondary = "association", lazy="subquery")

class User(db.Model):
    id = db.Column(db.Integer(), primary_key = True)
    username = db.Column(db.String(100), unique = True)
    password = db.Column(db.String(50))
      
class Admin(db.Model):
    id = db.Column(db.Integer(), primary_key = True)
    username = db.Column(db.String(100), unique = True)
    password = db.Column(db.String(50))
    
class Association(db.Model):
    show_id = db.Column(db.Integer(), db.ForeignKey("show.id"), primary_key = True)
    user_id = db.Column(db.Integer(), db.ForeignKey("user.id"), primary_key = True)
    tickets = db.Column(db.Integer())
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())
# db.init_app(app)
app.app_context().push() 

#=========================USER========================================================================================

@app.route('/user/new', methods=['POST'])
def user_signup():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_user = User(username=data['username'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'Registered successfully'}), 200

@app.route('/user/login', methods=['POST'])
def user_login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Bad credentials'}), 401
    access_token = create_access_token(identity=user.username)
    return jsonify({'access_token': access_token}), 200

@app.route("/user/venue", methods = ["GET","POST"])
@jwt_required()
def user_venue_show_details():
    venues = get_venues()
    shows = get_shows()
    return json.dumps({'venues':venues,
                       'shows':shows}), 200

@app.route('/user/book/<id>', methods = ["GET", "POST"])
@jwt_required()
def book_show(id): 
    data = request.get_json()
    uname = get_jwt_identity()
    u_id = User.query.filter_by(username=uname).first().id
    sho = Show.query.filter_by(id=id).first()
    vnu = Venue.query.filter_by(id=sho.venue_id).first()
    temp = int(vnu.capacity) - int(data["tickets"])
    if(temp<0): #to check if the show is booked
        return jsonify({'message':'Trying to book more tickets than available'}), 200
    else:
        if(Association.query.filter_by(show_id=id, user_id=u_id).all() == []):
            assn = Association(show_id=id, user_id=int(u_id), tickets=data["tickets"])
            db.session.add(assn)
            vnu.capacity = temp
            db.session.commit()
            return jsonify({'message':'Tickets booked successfuly '}),200
        else:
            vnu.capacity = temp
            a = Association.query.filter_by(show_id=id, user_id=u_id).all()  
            a[0].tickets = int(a[0].tickets) + int(data["tickets"])
            db.session.commit()
            return jsonify({'message':'Tickets booked successfuly '}),200
        
@app.route("/user/bookings", methods= ["GET","POST"])
@jwt_required()
def user_bookings(): #displays all the shows user has booked
        uname = get_jwt_identity()
        u_id = User.query.filter_by(username=uname).first().id
        venues = get_venues()
        assn = get_associations()
        bookings = get_bookings(u_id)
        return json.dumps({'venues':venues,
                           'bookings':bookings,
                           'associations':assn}), 200

#===============================ADMIN==============================================================================
@app.route('/admin/new', methods=['POST'])
def admin_signup():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_admin = Admin(username=data['username'], password=hashed_password)
    db.session.add(new_admin)
    db.session.commit()
    return jsonify({'message': 'Registered successfully'}), 200


@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    admin = Admin.query.filter_by(username=data['username']).first()
    if not admin or not check_password_hash(admin.password, data['password']):
        return jsonify({'message': 'Bad credentials'}), 401
    access_token = create_access_token(identity=admin.username)
    return jsonify({'access_token': access_token}), 200

@app.route("/admin/venue", methods= ["GET","POST"])
@jwt_required()
def venue_show_Details(): 
    venues = get_venues()
    shows = get_shows()
    return json.dumps({'venues':venues,
                       'shows':shows}), 200

@app.route("/admin/add_venue", methods= ["POST"])
def add_venue():
    data = request.get_json()
    vnu = Venue(name=data["name"], place=data["place"], location= data["location"], capacity=data["capacity"])
    db.session.add(vnu)
    db.session.commit()
    return jsonify({'message': 'Venue Added successfully'}), 200

@app.route("/admin/edit_venue/<id>", methods= ["POST"])
def edit_venue(id):
    data = request.get_json()
    vnu = Venue.query.get(id)
    vnu.name = data.get("ename") 
    vnu.place=data.get("eplace")
    vnu.location= data.get("elocation")
    vnu.capacity=data.get("ecapacity")
    db.session.commit()
    return jsonify({'message': 'Venue Edited successfully'}), 200

@app.route("/admin/venue/delete/<id>")
def del_venue(id):
        vnu = Venue.query.get(id)
        db.session.delete(vnu)
        db.session.commit()
        return jsonify({'message': 'Venue deleted successfully'}), 200

@app.route("/admin/add_show/<vid>", methods= ["POST"])
def add_show(vid):
    data = request.get_json()
    sho = Show(name=data["sname"], rating=data["rating"], timing= data["timing"], ticket_price=data["price"],  tags= data["tags"], venue_id= vid)
    db.session.add(sho)
    db.session.commit()
    return jsonify({'message': 'Show Added successfully'}), 200

@app.route("/admin/edit_show/<id>", methods= ["POST"])
def edit_show(id):
    data = request.get_json()
    sho = Show.query.get(id)
    sho.name = data.get("esname") 
    sho.rating=data.get("erating")
    sho.timing= data.get("etiming")
    sho.ticket_price=data.get("eprice")
    db.session.commit()
    return jsonify({'message': 'Show Edited successfully'}), 200

@app.route("/admin/show/delete/<id>")
def del_show(id):
        sho = Show.query.get(id)
        db.session.delete(sho)
        db.session.commit()
        return jsonify({'message': 'Show deleted successfully'}), 200

@cache.cached(timeout=50, key_prefix='get_shows')
def get_shows():
    dict_show = []
    start = perf_counter_ns()
    venues = Venue.query.all()
    for venue in venues:
        sho = []
        for show in venue.shows:
            sho.append({'id':show.id, 
                        'name':show.name,
                        'timing':show.timing,
                        'rating':show.rating,
                        'ticket_price':show.ticket_price,
                        'tags':show.tags})
        dict_show.append({'vid':venue.id,
                           'shows':sho})    
    stop = perf_counter_ns()
    print("Time Taken for Shows", stop - start)
    return dict_show

@cache.cached(timeout=50, key_prefix='get_venues')
def get_venues():
    dict_venue=[]
    start = perf_counter_ns()
    venues = Venue.query.all()
    for venue in venues:
        dict_venue.append({'id':venue.id, 
                                'name':venue.name, 
                                'place':venue.place,
                                'location':venue.location, 
                                'capacity':venue.capacity})
    stop = perf_counter_ns()
    print("Time Taken for Venues", stop - start)
    return dict_venue

def get_bookings(id):
    dict_bookings=[]
    bookings = User.query.get(id).shows
    for booking in bookings:
        dict_bookings.append({'sname':booking.name,
                              'rating':booking.rating,
                              'timing':booking.timing,
                              'ticket_price':booking.ticket_price,
                              'tags':booking.tags,
                              'venue_id':booking.venue_id
                              })
    return dict_bookings

def get_associations():
    dict_assn=[]
    associations = Association.query.all()
    for association in associations:
        dict_assn.append({'show_id':association.show_id,
                          'user_id':association.user_id,
                          'tickets':association.tickets
                          })
    return dict_assn
#=================================================== SEARCH ==================================

@app.route("/search", methods = ["GET","POST"])
def search_venue():
    venues = get_venues()
    shows = get_shows()
    return json.dumps({'venues':venues,
                       'shows':shows}), 200

#==============================================================================================

@app.route("/venue/export/<id>")
def trigger_celery_job(id):
    a = generate_csv.delay(id)
    return {
        "Task_ID" : a.id,
        "Task_State" : a.state,
        "Task_Result" : a.result
    }

@app.route("/status/<id>")
def check_status(id):
    res = AsyncResult(id, app = celery)
    return {
        "Task_ID" : res.id,
        "Task_State" : res.state,
        "Task_Result" : res.result
    }

@app.route("/download-file")
def download_file():
    return send_file("static/data.csv")

@app.route('/', methods=['GET'])
def start():
    return render_template("login.html")
    
if __name__ == '__main__':
    app.run(debug=True)