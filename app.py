from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from forms import RegistrationForm, LoginForm
import MySQLdb.cursors
import re
from flask_dance.contrib.google import make_google_blueprint, google
from flask_mail import Mail, Message
import pandas as pd
import matplotlib.pylab as plt
import seaborn as sns
import os
from decimal import Decimal

app = Flask(__name__)
google_blueprint = make_google_blueprint(
    client_id="666426612022-ncopuubkoer69h1hrq3qkig6sjdjvtfg.apps.googleusercontent.com",
    client_secret="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",
    scope=["profile", "email"],
    redirect_to="google_login"
)
app.register_blueprint(google_blueprint, url_prefix="/login")

app.secret_key = 'WealthWise'
enc = Bcrypt(app)

google_client_id="666426612022-ncopuubkoer69h1hrq3qkig6sjdjvtfg.apps.googleusercontent.com"

#Database
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'wealthwise'
mysql = MySQL(app)

#Mailpit 
app.config['MAIL_SERVER'] = 'localhost'
app.config['MAIL_PORT'] = 1025
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = None
app.config['MAIL_PASSWORD'] = None
app.config['MAIL_DEFAULT_SENDER'] = 'noreply@wealthwise.com'

mail = Mail(app)

app.config['WTF_CSRF_ENABLED'] = True

@app.route('/')
def home():
    return redirect(url_for('login'))

def is_email(identifier):
    return re.match(r'^\S+@\S+\.\S+$', identifier)

@app.route('/login', methods=['GET', 'POST'])
def login():
    log = LoginForm()
    if log.validate_on_submit():
        input_data = log.email_or_phone.data.strip()
        pw = log.password.data

        try:
            
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

            if is_email(input_data):
                cursor.execute('SELECT * FROM users WHERE email = %s', (input_data,))
            else:
                cursor.execute('SELECT * FROM users WHERE phone_number = %s', (input_data,))

            account = cursor.fetchone()

            if account:
                stored_hashed_pw = account['password_hash']
                full_name = account['full_name']
                email = account['email']
                if enc.check_password_hash(stored_hashed_pw, pw):
                    flash('Login Successful', 'success')
                    
                    msg = Message("Login Notification", recipients=[email])
                    msg.html = render_template("welcome_login.html", full_name=full_name)
                    mail.send(msg)
                    
                    return redirect(url_for('dashboard',user_id=account['id']))
                else:
                    flash('Invalid password', 'danger')
                    print("Invalid password")  # Debug line
            else:
                flash('User not registered or invalid credentials', 'danger')

            cursor.close()
          
        except Exception as e:
            flash(f'Error occurred: {e}', 'danger')
            mysql.connection.rollback()

    return render_template('login.html', form=log)

@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if resp.ok:
        user_info = resp.json()
        email = user_info["email"]
        name = user_info["name"]

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()

        if not account:
            # User doesn't exist, insert them
            cursor.execute('''
                INSERT INTO users (full_name, email, phone_number, address, password_hash, account_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (name, email, None, None, None, 'Google'))
            mysql.connection.commit()

        flash(f"Logged in as {name} ({email}) via Google", "success")
        
        return redirect(url_for("dashboard",user_id=account['id']))
          

    flash("Failed to log in via Google", "danger")
    return redirect(url_for("login"))

@app.route('/registration', methods=['GET', 'POST'])
def registration():
    form = RegistrationForm()
    if form.validate_on_submit():
        full_name = form.full_name.data
        email = form.email.data
        phone_num = form.phone_num.data
        address = form.address.data
        pw = form.password.data
        account_type = form.acc_type.data

        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT * FROM users WHERE phone_number=%s OR email=%s', (phone_num, email))
            account = cursor.fetchone()
            if account:
                if account['phone_number'] == phone_num:
                    flash('Phone Number Already Registered! Please use a new number', 'danger')
                elif account['email'] == email:
                    flash('Email Already Registered! Please use a new email', 'danger')
                return redirect(url_for('registration'))
            else:
                hash_pw = enc.generate_password_hash(pw).decode('utf-8')
                cursor.execute('''
                    INSERT INTO users (full_name, email, phone_number, address, password_hash, account_type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (full_name, email, phone_num, address, hash_pw, account_type))

                mysql.connection.commit()
                cursor.close()
                flash('You Have Successfully Registered!', 'success')
                msg = Message("Welcome to WealthWise!", recipients=[email])
                msg.html = render_template("welcome_mail.html", full_name=full_name)
                mail.send(msg)
                return redirect(url_for('login'))

        except Exception as e:
            flash(f'Error occurred: {e}', 'danger')
            mysql.connection.rollback()

    return render_template('register.html', form=form)

@app.route('/dashboard/<int:user_id>')
def dashboard(user_id):
    try:
        cursor=mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id=%s',(user_id,))
        user=cursor.fetchone()
        
        if not user:
            flash('User not found','danger')
            return redirect(url_for('login'))
        
        cursor.execute('''SELECT transaction_type,category,amount,date
                       FROM transactions
                       WHERE user_id=%s''',(user_id,))
        transactions=cursor.fetchall()
        
        total_income = Decimal('0.0')
        total_exp = Decimal('0.0')
        needs_spent = Decimal('0.0')
        wants_spent = Decimal('0.0')
        savings_saved = Decimal('0.0')
        
        for transaction in transactions:
            amount=transaction['amount']
            transaction_type=transaction['transaction_type']
            category=transaction['category'].lower()
            
            if transaction_type=='income':
                total_income=total_income+amount
            
            if transaction_type=='expense':
                total_exp=total_exp+amount
                
            if transaction_type=='expense' and category=='needs':
                needs_spent=needs_spent + amount
            
            if transaction_type=='expense' and category=='wants':
                wants_spent=wants_spent+amount
                
            if transaction_type=='income' and category=='savings':
                savings_saved=savings_saved+amount
            
        cursor.execute('SELECT * FROM budget_allocations WHERE user_id=%s',(user_id,))
        budget=cursor.fetchone()
        
        if not budget:
            cursor.execute('''
                           INSERT INTO budget_allocations (user_id,needs_percent,wants_percent,savings_percent,total_budget)
                           VALUES(%s,50.00,30.00,20.00,%s)
                           ''',(user_id,total_income))
            mysql.connection.commit()
            cursor.execute('SELECT * FROM budget_allocations WHERE user_id=%s',(user_id,))
            budget=cursor.fetchone()
            
        if not budget:
            budget={
                'needs_percent':50.00,
                'wants_percent':30.00,
                'savings_percent':20.00,
                'total_budget':total_income
            }
            print(f"Warning:Budget allocation failed fot user{user_id},using default 50/30/20")
            
        needs_limit=(Decimal(budget['needs_percent'])/100)*total_income
        wants_limit=(Decimal(budget['wants_percent'])/100)*total_income
        needs_spent_percent=(needs_spent/needs_limit*100)if needs_limit>0 else Decimal('0.0')
        wants_spent_percent=(wants_spent/wants_limit*100)if wants_limit>0 else Decimal('0.0')
        
        warning_per=Decimal('80.0')
        email_sent=False
        
        if needs_spent_percent>warning_per:
            status = "Exceeded" if needs_spent_percent >= 100 else "Approaching"
            msg = Message(f"Budget Warning: Needs Spending {status.capitalize()}", recipients=[user['email']])
            msg.html = render_template(
                "warning.html",
                user_id=user['id'] ,
                full_name=user['full_name'],
                category="Needs",
                spent=needs_spent,
                limit=needs_limit,
                percent=needs_spent_percent,
                status=status
            )
            mail.send(msg)
            email_sent = True
            
        if wants_spent_percent >= warning_per:
            status = "Has Exceeded" if wants_spent_percent >= 100 else "Is Approaching"
            msg = Message(f"Budget Warning: Wants Spending {status.capitalize()}", recipients=[user['email']])
            msg.html = render_template(
                "warning.html",
                user_id=user['id'] ,
                full_name=user['full_name'],
                category="Wants",
                spent=wants_spent,
                limit=wants_limit,
                percent=wants_spent_percent,
                status=status
            )
            mail.send(msg)
            email_sent = True
        
        if email_sent:
            flash('Warning: You have been notified via email about your budget limits.', 'warning')
        
        
            
        return render_template('dashboard.html',user=user,total_income=total_income,total_exp=total_exp,needs_spent=needs_spent,wants_spent=wants_spent,savings_saved=savings_saved,budget=budget)
    
    except Exception as e:
        flash(f"Error loading dashboard:{e}",'danger')
        mysql.connection.rollback()
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
