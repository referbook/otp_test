# Import statements
import os

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from twilio.rest import Client
import random
import secrets
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = secrets.token_hex(24)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=2)  # Set session timeout to 2 minutes

# PostgreSQL credentials for otp_auth database
otp_auth_params = {
    'dbname': 'otp_auth',
    'user': 'postgres',
    'password': 'pk2512',
    'host': '127.0.0.1',
    'port': '5432',
}

# PostgreSQL credentials for todo_list database
todo_list_params = {
    'dbname': 'to_do',
    'user': 'postgres',
    'password': 'pk2512',
    'host': '127.0.0.1',
    'port': '5432',
}

# Establish connections to the PostgreSQL databases
conn_otp_auth = psycopg2.connect(**otp_auth_params)
cur_otp_auth = conn_otp_auth.cursor()

conn_todo_list = psycopg2.connect(**todo_list_params)
cur_todo_list = conn_todo_list.cursor()

# Create the otp_auth table if it doesn't exist
cur_otp_auth.execute("""
    CREATE TABLE IF NOT EXISTS otp_auth (
        phone_number VARCHAR(15) PRIMARY KEY,
        otp VARCHAR(4),
        count INTEGER DEFAULT 1,
        last_verified_time TIMESTAMP
    )
""")
conn_otp_auth.commit()

# Create the todo_list table if it doesn't exist
cur_todo_list.execute("""
    CREATE TABLE IF NOT EXISTS todo_list (
        phone_number VARCHAR(15),
        task TEXT,
        PRIMARY KEY (phone_number, task)
    )
""")
conn_todo_list.commit()

# Twilio credentials
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
client = Client(account_sid, auth_token)

# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin'


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/send_otp', methods=['POST'])
def send_otp():
    user_phone_number = request.form.get('phone_number')
    user_name = request.form.get('name')
    otp = generate_otp()
    session.permanent = True  # Make the session permanent
    session['user_name'] = user_name

    # Check if the phone number exists in the otp_auth table
    cur_otp_auth.execute(
        sql.SQL("SELECT * FROM otp_auth WHERE phone_number = {}").format(sql.Literal(user_phone_number)))
    existing_record = cur_otp_auth.fetchone()

    if existing_record:
        # If the phone number exists, update the OTP and increment the count
        cur_otp_auth.execute(sql.SQL("""
            UPDATE otp_auth
            SET otp = {},
                count = count + 1
            WHERE phone_number = {}
        """).format(sql.Literal(otp), sql.Literal(user_phone_number)))
    else:
        # If the phone number doesn't exist, insert a new record
        cur_otp_auth.execute("""
            INSERT INTO otp_auth (phone_number, otp, count)
            VALUES (%s, %s, 1)
        """, (user_phone_number, otp))

    conn_otp_auth.commit()

    # Retrieve the to-do list for the user
    cur_todo_list.execute(
        sql.SQL("SELECT task FROM todo_list WHERE phone_number = {}").format(sql.Literal(user_phone_number)))
    todo_list = cur_todo_list.fetchall()

    # Reset OTP verification status in the session
    session['otp_verified'] = False
    send_otp_message(user_phone_number, otp)
    session['phone_number'] = user_phone_number
    session['otp'] = otp
    session['todo_list'] = todo_list

    return redirect(url_for('verify_otp', phone_number=user_phone_number))


@app.route('/verify_otp/<phone_number>', methods=['GET', 'POST'])
def verify_otp(phone_number):
    error_message = None  # Initialize error message variable

    if request.method == 'POST':
        user_otp = request.form.get('otp')
        stored_otp = session.get('otp')

        if stored_otp and user_otp == stored_otp:
            # Update the last_verified_time in the otp_auth table
            cur_otp_auth.execute(sql.SQL("""
                UPDATE otp_auth
                SET last_verified_time = {}
                WHERE phone_number = {}
            """).format(sql.Literal(datetime.now()), sql.Literal(phone_number)))

            conn_otp_auth.commit()

            session['otp_verified'] = True  # Set OTP verification status
            return redirect(url_for('welcome'))

        else:
            error_message = 'Invalid OTP. Please try again.'

    return render_template('verify_otp.html', phone_number=phone_number, error_message=error_message)


@app.route('/welcome')
def welcome():
    if not session.get('otp_verified'):
        return redirect(url_for('index'))
    user_name = session.get('user_name', 'Guest')
    return render_template('welcome.html', user_name=user_name)


@app.route('/todo_list', methods=['GET', 'POST'])
def todo_list():
    if not session.get('otp_verified'):
        return redirect(url_for('index'))
    user_phone_number = session.get('phone_number')

    if request.method == 'POST':
        new_task = request.form.get('new_task')
        if new_task:
            # Check if the phone number exists in the todo_list table
            cur_todo_list.execute(
                sql.SQL("SELECT task FROM todo_list WHERE phone_number = {}").format(sql.Literal(user_phone_number)))
            existing_task = cur_todo_list.fetchone()

            if existing_task:
                # If the phone number exists, insert a new record with the same phone number and the updated task
                cur_todo_list.execute("""
                    INSERT INTO todo_list (phone_number, task)
                    VALUES (%s, %s)
                """, (user_phone_number, new_task))
            else:
                # If the phone number doesn't exist, insert a new record
                cur_todo_list.execute("""
                    INSERT INTO todo_list (phone_number, task)
                    VALUES (%s, %s)
                """, (user_phone_number, new_task))

            conn_todo_list.commit()

    # Retrieve the to-do list for the user
    cur_todo_list.execute(
        sql.SQL("SELECT task FROM todo_list WHERE phone_number = {}").format(sql.Literal(user_phone_number)))
    todo_list = cur_todo_list.fetchall()

    return render_template('todo_list.html', todo_list=todo_list)


# Helper functions
def generate_otp():
    return str(random.randint(1000, 9999))


def send_otp_message(to, otp):
    message = client.messages.create(
        body=f'Your OTP is: {otp}',
        from_=twilio_phone_number,
        to=to
    )
    print(f"OTP sent with SID: {message.sid}")


if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=True)
