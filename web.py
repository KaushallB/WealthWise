import streamlit as st
import time
from datetime import datetime

# Mock AuthManager (Replace with your actual authentication logic)
class AuthManager:
    def __init__(self):
        # Mock user data for demonstration
        self.users = {
            "test@example.com": {"password": "password", "name": "Test User"},
            "user@test.com": {"password": "userpass", "name": "Another User"}
        }

    def login_user(self, email, password):
        if email in self.users and self.users[email]["password"] == password:
            return True
        return False

    def get_user_name(self, email):
        if email in self.users:
            return self.users[email]["name"]
        return None

# Session state for tracking login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""

# --- UI ---
st.title("Syntego")
st.write("An AI-powered finance tracker.")

tab1, tab2 = st.tabs(["Login", "Register"])

with tab1:
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")
    auth = AuthManager() #initialize অথ here

    if login_btn:
        if auth.login_user(email, password):
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.success("Login successful! Redirecting ...")
            time.sleep(1.5)
            st.rerun()  # Rerun to update the UI based on logged_in state
        else:
            st.error("Invalid email or password.")

with tab2:
    st.subheader("Register")
    new_email = st.text_input("Email")
    new_password = st.text_input("Password", type="password")
    name = st.text_input("Name")
    register_btn = st.button("Register")
    auth = AuthManager() #initialize অথ here

    if register_btn:
        #  Simplified registration (in real app, handle password hashing, etc.)
        if new_email in auth.users:
            st.error("Email already exists. Please use a different email.")
        else:
            auth.users[new_email] = {"password": new_password, "name": name}  # Store new user
            st.success("Registration successful! Please log in.")
            #st.rerun() #removed auto rerurn

# --- Main App ---
if st.session_state.logged_in:
    user_name = auth.get_user_name(st.session_state.user_email)
    st.write(f"Welcome, {user_name}!")
    st.write("This is your personalized finance dashboard.")

    # --- Sample Data for Demonstration ---
    income_data = [
        {"source": "Salary", "amount": 50000, "date": datetime(2024, 1, 15)},
        {"source": "Freelance", "amount": 20000, "date": datetime(2024, 1, 20)},
        {"source": "Salary", "amount": 55000, "date": datetime(2024, 2, 15)},
    ]
    expense_data = [
        {"category": "Needs", "amount": 15000, "date": datetime(2024, 1, 5)},
        {"category": "Wants", "amount": 10000, "date": datetime(2024, 1, 10)},
        {"category": "Savings", "amount": 25000, "date": datetime(2024, 1, 25)},
        {"category": "Needs", "amount": 16000, "date": datetime(2024, 2, 5)},
        {"category": "Wants", "amount": 12000, "date": datetime(2024, 2, 12)},
    ]

    # --- Data Display ---
    st.subheader("Your Finances")
    total_income = sum(item["amount"] for item in income_data)
    total_expenses = sum(item["amount"] for item in expense_data)

    st.write(f"Total Income: {total_income}")
    st.write(f"Total Expenses: {total_expenses}")

    # --- 50/30/20 Calculation ---
    needs = sum(item["amount"] for item in expense_data if item["category"] == "Needs")
    wants = sum(item["amount"] for item in expense_data if item["category"] == "Wants")
    savings = sum(item["amount"] for item in expense_data if item["category"] == "Savings")

    if total_expenses > 0:
        needs_percentage = (needs / total_expenses) * 100
        wants_percentage = (wants / total_expenses) * 100
        savings_percentage = (savings / total_expenses) * 100
    else:
        needs_percentage = 0
        wants_percentage = 0
        savings_percentage = 0

    st.write(f"Needs: {needs_percentage:.2f}%")
    st.write(f"Wants: {wants_percentage:.2f}%")
    st.write(f"Savings: {savings_percentage:.2f}%")
