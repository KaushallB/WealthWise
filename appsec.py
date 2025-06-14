from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
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
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
import logging
from functools import wraps  # CHANGED: Added for login_required decorator

app = Flask(__name__)
google_blueprint = make_google_blueprint(
    client_id="666426612022-ncopuubkoer69h1hrq3qkig6sjdjvtfg.apps.googleusercontent.com",
    client_secret="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",
    scope=["profile", "email"],
    redirect_to="google_login"
)
app.register_blueprint(google_blueprint, url_prefix="/login")

# CHANGED: Use a stronger secret key for sessions
app.secret_key = os.urandom(24).hex()  # Generates a random secure key
enc = Bcrypt(app)

google_client_id = "666426612022-ncopuubkoer69h1hrq3qkig6sjdjvtfg.apps.googleusercontent.com"

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Database
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'wealthwise'
mysql = MySQL(app)

# Mailpit
app.config['MAIL_SERVER'] = 'localhost'
app.config['MAIL_PORT'] = 1025
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = None
app.config['MAIL_PASSWORD'] = None
app.config['MAIL_DEFAULT_SENDER'] = 'noreply@wealthwise.com'
mail = Mail(app)

app.config['WTF_CSRF_ENABLED'] = True

# CHANGED: Custom login_required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(user_id, *args, **kwargs):
        if 'user_id' not in session:
            logging.debug(f"Unauthorized access attempt to user_id {user_id}: No session")
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        if int(session['user_id']) != int(user_id):
            logging.debug(f"Unauthorized access attempt: Session user_id {session['user_id']} does not match requested user_id {user_id}")
            flash('You are not authorized to access this user’s data.', 'danger')
            return redirect(url_for('login'))
        return f(user_id, *args, **kwargs)
    return decorated_function

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
                    # CHANGED: Store user_id in session
                    session['user_id'] = account['id']
                    logging.debug(f"User {account['id']} logged in via email/phone")
                    flash('Login Successful', 'success')
                    
                    msg = Message("Login Notification", recipients=[email])
                    msg.html = render_template("welcome_login.html", full_name=full_name)
                    mail.send(msg)
                    
                    return redirect(url_for('dashboard', user_id=account['id']))
                else:
                    flash('Invalid password', 'danger')
                    logging.debug(f"Invalid password attempt for {input_data}")
            else:
                flash('User not registered or invalid credentials', 'danger')
                logging.debug(f"No account found for {input_data}")

            cursor.close()
          
        except Exception as e:
            flash(f'Error occurred: {e}', 'danger')
            logging.error(f"Login error: {e}")
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
            cursor.execute('''
                INSERT INTO users (full_name, email, phone_number, address, password_hash, account_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (name, email, None, None, None, 'Google'))
            mysql.connection.commit()
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            account = cursor.fetchone()

        # CHANGED: Store user_id in session
        session['user_id'] = account['id']
        logging.debug(f"User {account['id']} logged in via Google")
        flash(f"Logged in as {name} ({email}) via Google", "success")
        
        return redirect(url_for("dashboard", user_id=account['id']))
          
    flash("Failed to log in via Google", "danger")
    logging.debug("Google login failed")
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
            logging.error(f"Registration error: {e}")
            mysql.connection.rollback()

    return render_template('register.html', form=form)

# CHANGED: Added logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    logging.debug("User logged out")
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard/<int:user_id>')
@login_required  # CHANGED: Applied login_required decorator
def dashboard(user_id):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))
        user = cursor.fetchone()
        
        # CHANGED: Removed redundant user check (handled by decorator)
        cursor.execute('''SELECT transaction_type, category, amount, date
                       FROM transactions
                       WHERE user_id=%s''', (user_id,))
        transactions = cursor.fetchall()
        
        total_income = Decimal('0.0')
        total_exp = Decimal('0.0')
        needs_spent = Decimal('0.0')
        wants_spent = Decimal('0.0')
        savings_saved = Decimal('0.0')
        
        for transaction in transactions:
            amount = transaction['amount']
            transaction_type = transaction['transaction_type']
            category = transaction['category'].lower()
            
            if transaction_type == 'income':
                total_income += amount
                if category == 'savings':
                    savings_saved += amount
            if transaction_type == 'expense':
                total_exp += amount
                if category == 'needs':
                    needs_spent += amount
                if category == 'wants':
                    wants_spent += amount
            
        cursor.execute('SELECT * FROM budget_allocations WHERE user_id=%s', (user_id,))
        budget = cursor.fetchone()
        
        if not budget and total_income > 0:
            cursor.execute('''
                           INSERT INTO budget_allocations (user_id, needs_percent, wants_percent, savings_percent, total_budget)
                           VALUES (%s, %s, %s, %s, %s)
                           ''', (user_id, Decimal('50.00'), Decimal('30.00'), Decimal('20.00'), total_income))
            mysql.connection.commit()
            cursor.execute('SELECT * FROM budget_allocations WHERE user_id=%s', (user_id,))
            budget = cursor.fetchone()
            
        if not budget:
            budget = {
                'needs_percent': Decimal('50.00'),
                'wants_percent': Decimal('30.00'),
                'savings_percent': Decimal('20.00'),
                'total_budget': total_income
            }
            logging.warning(f"Budget allocation not created for user {user_id}, using default 50/30/20")
        
        needs_percent = Decimal(budget['needs_percent']) if budget.get('needs_percent') else Decimal('50.00')
        wants_percent = Decimal(budget['wants_percent']) if budget.get('wants_percent') else Decimal('30.00')
        savings_percent = Decimal(budget['savings_percent']) if budget.get('savings_percent') else Decimal('20.00')
        
        needs_limit = (needs_percent / 100) * total_income if needs_percent > 0 else Decimal('0.0')
        wants_limit = (wants_percent / 100) * total_income if wants_percent > 0 else Decimal('0.0')
        
        needs_spent_percent = Decimal('0.0')
        wants_spent_percent = Decimal('0.0')
        
        if total_income > 0 and needs_limit > 0 and needs_percent > 0:
            needs_spent_percent = (needs_spent / needs_limit) * 100
        if total_income > 0 and wants_limit > 0 and wants_percent > 0:
            wants_spent_percent = (wants_spent / wants_limit) * 100
        
        warning_per = Decimal('80.0')
        email_sent = False
        
        if total_income > 0 and needs_limit > 0 and needs_percent > 0 and needs_spent_percent > warning_per:
            status = "Exceeded" if needs_spent_percent >= 100 else "Approaching"
            msg = Message(f"Budget Warning: Needs Spending {status.capitalize()}", recipients=[user['email']])
            msg.html = render_template(
                "warning.html",
                user_id=user['id'],
                full_name=user['full_name'],
                category="Needs",
                spent=needs_spent,
                limit=needs_limit,
                percent=needs_spent_percent,
                status=status
            )
            mail.send(msg)
            email_sent = True
            
        if total_income > 0 and wants_limit > 0 and wants_percent > 0 and wants_spent_percent >= warning_per:
            status = "Has Exceeded" if wants_spent_percent >= 100 else "Is Approaching"
            msg = Message(f"Budget Warning: Wants Spending {status.capitalize()}", recipients=[user['email']])
            msg.html = render_template(
                "warning.html",
                user_id=user['id'],
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
        
        logging.debug(f"Rendering dashboard for user {user_id}")
        return render_template('dashboard.html', user=user, total_income=total_income, total_exp=total_exp, needs_spent=needs_spent, wants_spent=wants_spent, savings_saved=savings_saved, budget=budget)
    
    except Exception as e:
        flash(f"Error loading dashboard: {e}", 'danger')
        logging.error(f"Dashboard error for user {user_id}: {e}")
        mysql.connection.rollback()
        return redirect(url_for('login'))
    finally:
        cursor.close()

# Initializing OLLAMA
model = OllamaLLM(model="llama3")
template = """
You are a financial advisor for WealthWise, a budgeting app for students and small businesses in Nepal. Provide concise, accurate financial advice (under 100 words) in NPR, focusing on budgeting and differentiating needs vs. wants. Needs are essential expenses (e.g., rent, groceries, utilities); wants are non-essential (e.g., entertainment, dining out). Use the user's financial data, ensuring amounts are in NPR. Stay professional, avoid non-financial topics, and do not ask questions unless prompted. If the query is unclear, suggest asking about budgeting or expenses.

User's financial data: {financial_data}

Conversation history: {context}

Question: {question}

Answer:
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

@app.route('/chatbot/<int:user_id>', methods=['GET', 'POST'])
@login_required  # CHANGED: Applied login_required decorator
def chatbot(user_id):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))
        user = cursor.fetchone()
        full_name = user['full_name']
        
        cursor.execute('''SELECT transaction_type, category, SUM(amount) as total
                        FROM transactions
                        WHERE user_id=%s
                        GROUP BY transaction_type, category''', (user_id,))
        transactions = cursor.fetchall()
        
        total_income = Decimal('0.0')
        needs_spent = Decimal('0.0')
        wants_spent = Decimal('0.0')
        savings_saved = Decimal('0.0')
        
        for transaction in transactions:
            amount = Decimal(str(transaction['total'] or '0.0'))
            transaction_type = transaction['transaction_type']
            category = transaction['category'].lower()
        
            if transaction_type == 'income':
                total_income += amount
                if category == 'savings':
                    savings_saved += amount
            elif transaction_type == 'expense':
                if category == 'needs':
                    needs_spent += amount
                elif category == 'wants':
                    wants_spent += amount
        
        financial_data = (
            f"Total Income: NPR {float(total_income * 100):.2f}, "
            f"Needs Spent: NPR {float(needs_spent * 100):.2f} (Budget: 50%), "
            f"Wants Spent: NPR {float(wants_spent * 100):.2f} (Budget: 30%), "
            f"Savings: NPR {float(savings_saved * 100):.2f} (Goal: 20%)"
        )
        
        context = request.args.get('context', '') or request.form.get('context', '')
        
        if request.method == 'POST':
            user_message = request.form.get('message', '').strip()
            if not user_message:
                return jsonify({'error': 'Please enter a message'}), 400
            
            responseofai = chain.invoke({
                "financial_data": financial_data,
                "context": context,
                "question": user_message
            })

            new_context = f"{context}\nUser: {user_message}\nAI: {responseofai}".strip()
            logging.debug(f"Chatbot response for user {user_id}")
            return jsonify({'response': responseofai, 'context': new_context})
        
        logging.debug(f"Rendering chatbot for user {user_id}")
        return render_template('chatbot.html', user=user, full_name=full_name)
    
    except Exception as e:
        logging.error(f"Chatbot error for user {user_id}: {e}")
        return jsonify({'error': f'Error: {str(e)}'}), 500
    finally:
        cursor.close()

if __name__ == '__main__':
    app.run(debug=True)