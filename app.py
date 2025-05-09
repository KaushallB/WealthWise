from flask import Flask, render_template, request, redirect, url_for, flash, jsonify,session
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
from datetime import datetime
from decimal import Decimal
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate


app = Flask(__name__)



google_blueprint = make_google_blueprint(
    client_id="666426612022-ncopuubkoer69h1hrq3qkig6sjdjvtfg.apps.googleusercontent.com",
    client_secret="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",
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"
    ],
    redirect_url="/login/google/authorized"
)
app.register_blueprint(google_blueprint, url_prefix="/login")


app.secret_key = 'WealthWise'
enc = Bcrypt(app)

google_client_id="666426612022-ncopuubkoer69h1hrq3qkig6sjdjvtfg.apps.googleusercontent.com"

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

def is_logged_in():
    return 'user_id' in session


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
                    
                    session['user_id']=account['id']
                    
                    msg = Message("Login Notification", recipients=[email])
                    msg.html = render_template("welcome_login.html", full_name=full_name)
                    mail.send(msg)
                    
                    return redirect(url_for('dashboard', user_id=account['id']))
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
            cursor.execute('''
                INSERT INTO users (full_name, email, phone_number, address, password_hash, account_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (name, email, None, None, None, 'Google'))
            mysql.connection.commit()
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            account = cursor.fetchone()

        if account:
                session['user_id'] = account['id']
                flash(f"Logged in as {name} ({email}) via Google", "success")
                return redirect(url_for("dashboard", user_id=account['id']))
       
        
        return redirect(url_for("dashboard", user_id=account['id']))
          
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
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard/<int:user_id>')
def dashboard(user_id):
    
    if not is_logged_in():
        flash('Please log in to access the dashboard.', 'danger')
        return redirect(url_for('login'))

    if session['user_id'] != user_id:
        flash('You are not authorized to access this dashboard.', 'danger')
        return redirect(url_for('logout'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('login'))
        
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
        
        # CHANGED: Only create budget if total_income > 0
        if not budget and total_income > 0:
            cursor.execute('''
                           INSERT INTO budget_allocations (user_id, needs_percent, wants_percent, savings_percent, total_budget)
                           VALUES (%s, %s, %s, %s, %s)
                           ''', (user_id, Decimal('50.00'), Decimal('30.00'), Decimal('20.00'), total_income))
            mysql.connection.commit()
            cursor.execute('SELECT * FROM budget_allocations WHERE user_id=%s', (user_id,))
            budget = cursor.fetchone()
            
        # CHANGED: Use Decimal for budget defaults and validate percentages
        if not budget:
            budget = {
                'needs_percent': Decimal('50.00'),
                'wants_percent': Decimal('30.00'),
                'savings_percent': Decimal('20.00'),
                'total_budget': total_income
            }
            print(f"Warning: Budget allocation not created for user {user_id}, using default 50/30/20")
        
        # CHANGED: Validate budget percentages to prevent zero or null values
        needs_percent = Decimal(budget['needs_percent']) if budget.get('needs_percent') else Decimal('50.00')
        wants_percent = Decimal(budget['wants_percent']) if budget.get('wants_percent') else Decimal('30.00')
        savings_percent = Decimal(budget['savings_percent']) if budget.get('savings_percent') else Decimal('20.00')
        
        # CHANGED: Ensure limits are calculated safely
        needs_limit = (needs_percent / 100) * total_income if needs_percent > 0 else Decimal('0.0')
        wants_limit = (wants_percent / 100) * total_income if wants_percent > 0 else Decimal('0.0')
        
        needs_spent_percent = Decimal('0.0')
        wants_spent_percent = Decimal('0.0')
        
        # CHANGED: Only calculate percentages if all conditions are strictly met
        if total_income > 0 and needs_limit > 0 and needs_percent > 0:
            needs_spent_percent = (needs_spent / needs_limit) * 100
        if total_income > 0 and wants_limit > 0 and wants_percent > 0:
            wants_spent_percent = (wants_spent / wants_limit) * 100
        
        warning_per = Decimal('80.0')
        email_sent = False
        
        # CHANGED: Only send warnings if calculations are valid
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
        
        return render_template('dashboard.html', user=user, total_income=total_income, total_exp=total_exp, needs_spent=needs_spent, wants_spent=wants_spent, savings_saved=savings_saved, budget=budget)
    
    except Exception as e:
        flash(f"Error loading dashboard: {e}", 'danger')
        mysql.connection.rollback()
        return redirect(url_for('login'))
    finally:
        cursor.close()

# Initializing OLLAMA
model = OllamaLLM(model="llama3")



@app.route('/chatbot/<int:user_id>',methods=['GET','POST'])
def chatbot(user_id):
    if not is_logged_in():
        flash('Please log in to access the chatbot.', 'danger')
        return redirect(url_for('login'))
    if session['user_id'] != user_id:
        flash('You are not authorized to access this chatbot.', 'danger')
        return redirect(url_for('logout'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))
        user = cursor.fetchone()
        full_name=user['full_name']
        management_type=user['account_type']
        
        if not user:
            return jsonify('SELECT * FROM users WHERE id=%s',(user_id,))  #Jsonify uses AJAX for realtime communication without reloading page raicha
        
        cursor.execute('''SELECT transaction_type, category, SUM(amount) as total
                        FROM transactions
                        WHERE user_id=%s
                        GROUP BY transaction_type, category''', (user_id,))
        transactions=cursor.fetchall()
        
        total_income = Decimal('0.0')
        needs_spent = Decimal('0.0')
        wants_spent = Decimal('0.0')
        savings_saved = Decimal('0.0')
        
        for transaction in transactions:
            amount=transaction['total']
            transaction_type=transaction['transaction_type']
            category=transaction['category'].lower()
        
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
            f"Total Income: ${float(total_income):.2f}, "
            f"Needs Spent: ${float(needs_spent):.2f} (Budget: 50%), "
            f"Wants Spent: ${float(wants_spent):.2f} (Budget: 30%), "
            f"Savings: ${float(savings_saved):.2f} (Goal: 20%)"
        )
        
        if request.method == 'POST':
            user_message = request.form.get('message', '').strip()
            context = request.form.get('context', '').strip()
            if not user_message:
                return jsonify({'response': 'Please enter a message.'}), 400
            
            if management_type == 'shop':
                    template = """
                    You are a financial advisor for WealthWise, a shop or business management and recommendation app for small businesses or shops in Nepal. 
                    Provide concise, accurate business advice (under 100 words) in NPR, focusing on maximizing profit, optimizing inventory, and managing expenses and help improve sales and reduce expenses . 
                    The average income of nepalese shops and businesses  depends on their sales and profit ranging from Rs 15000.00 to 50000.00 or above and also have to bear all the rent costs and other costs.
                    Use the user's financial data. Stay professional, avoid non-financial topics, and do not ask questions unless prompted. 
                    If the query is unclear, suggest asking about profit strategies or expense management.

                    User's financial data: {financial_data}

                    Conversation history: {context}

                    Question: {question}

                    Answer:
                    """
                
            if management_type=='personal':
                        template = """
                            You are a financial advisor for WealthWise, a finance management,adivising and recommendation app for  students in Nepal. Provide concise, accurate financial advice (under 100 words) in NPR, focusing on budgeting and differentiating needs vs. wants. 
                            are essential expenses (e.g., rent, groceries, utilities); wants are non-essential (e.g., entertainment, dining out). 
                            The average income of nepalese students is from around Rs 5000.00 to Rs 25000.00 and dont use $ and compare it with USD.
                            Use the user's financial data, and use nepali currency. Stay professional, avoid non-financial topics, and do not ask questions unless prompted. 
                            If the query is unclear, suggest asking about budgeting or expenses.

                            User's financial data: {financial_data}

                            Conversation history: {context}

                            Question: {question}

                            Answer:
                            """
            
            prompt = ChatPromptTemplate.from_template(template)
            chain = prompt | model
            
            responseofai=chain.invoke({
                "financial_data":financial_data,
                "context":context,
                "question":user_message
            })

            new_context=f"{context}\nUser:{user_message}\nAI:{responseofai}".strip()
            return jsonify({'response':responseofai,'context':new_context})
        return render_template('chatbot.html',user=user,full_name=full_name)
    
    except Exception as e:
        return jsonify({'response': f'Error: {str(e)}'}), 500

@app.route('/add_income/<int:user_id>',methods=['GET','POST'])
def add_income(user_id):
    if not is_logged_in or session['user_id']!=user_id:
        flash('Please log in to add income','danger')
        return redirect(url_for('logout'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id=%s',(user_id,))
        user=cursor.fetchone()
        if not user:
            flash('User not found','danger')
            return redirect(url_for('login'))

        cursor.execute("SELECT * FROM transactions WHERE user_id=%s AND transaction_type='income' ORDER BY date DESC LIMIT 5", (user_id,))
        recent_incomes = cursor.fetchall()
        
        if request.method=='POST':
            amount = request.form.get('amount')
            category = request.form.get('category')
            date = request.form.get('date')
            description = request.form.get('description')
            income_id = request.form.get('income_id')
            
            if not amount or not category or not date:
                flash('All fields are required.', 'danger')
                
            else:
                if income_id:
                    cursor.execute(
                        "UPDATE transactions SET amount=%s, category=%s, date=%s, description=%s WHERE id=%s AND user_id=%s",
                        (Decimal(amount), category, date, description, income_id, user_id)
                    )
                    mysql.connection.commit()
                    flash('Income updated successfully!', 'success')
                else: #adding
                    cursor.execute(
                        "INSERT INTO transactions (user_id, transaction_type, category, amount, date, description) VALUES (%s, 'income', %s, %s, %s, %s)",
                        (user_id, category, Decimal(amount), date, description)
                    )
                    mysql.connection.commit()
                    flash('Income added successfully!', 'success')
                return redirect(url_for('add_income', user_id=user_id))
        today=datetime.now().strftime('%Y-%m-%d')
        return render_template('add_income.html', user=user, today=today, recent_incomes=recent_incomes, income=None)
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard', user_id=user_id))
    
@app.route('/edit_income/<int:user_id>/<int:income_id>', methods=['GET'])
def edit_income(user_id, income_id):
    if not is_logged_in() or session['user_id'] != user_id:
        flash('Please log in to edit income.', 'danger')
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))
        user = cursor.fetchone()
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('login'))
        
        cursor.execute("SELECT * FROM transactions WHERE id=%s AND user_id=%s AND transaction_type='income'", (income_id, user_id))
        income = cursor.fetchone()
        if not income:
            flash('Income not found.', 'danger')
            return redirect(url_for('add_income', user_id=user_id))
        
        cursor.execute("SELECT * FROM transactions WHERE user_id=%s AND transaction_type='income' ORDER BY date DESC LIMIT 5", (user_id,))
        recent_incomes = cursor.fetchall()
        
        today = datetime.now().strftime('%Y-%m-%d')
        return render_template('add_income.html', user=user, today=today, recent_incomes=recent_incomes, income=income)
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard', user_id=user_id))
  
@app.route('/delete_income/<int:user_id>/<int:income_id>', methods=['POST'])
def delete_income(user_id, income_id):
    if not is_logged_in() or session['user_id'] != user_id:
        flash('Please log in to delete income.', 'danger')
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id=%s', (user_id,))
        user = cursor.fetchone()
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('login'))
        
        # Delete the income record
        cursor.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s AND transaction_type='income'", (income_id, user_id))
        mysql.connection.commit()
        
        flash('Income deleted successfully!', 'success')
        return redirect(url_for('add_income', user_id=user_id))
    
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('add_income', user_id=user_id))
   
if __name__ == '__main__':
    app.run(debug=True)