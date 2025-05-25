from flask_wtf import FlaskForm as FF
from wtforms import StringField,IntegerField,PasswordField,SelectField,SubmitField,DateField,FloatField
from wtforms.validators import DataRequired,EqualTo,ValidationError,Email
import re

#Validations made by me
def name_val(form,field):
    if not re.match("^[a-zA-z\s]+$",field.data):
        raise ValidationError('Name cannot should have only letters and spaces')
    
def number_val(form,field):
    if not re.match("^\+?\d{10,15}",field.data):
        raise ValidationError("Phone Number cannot contain only numbers")

def pw_val(form, field):
    print("Password entered:", field.data)  # Debugging line
    if not re.match("^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$", field.data):
        raise ValidationError("Password must be at least 8 characters with uppercase, lowercase, digits, and special characters")

def positive_amount(form, field):
    if not isinstance(field.data, (int, float)) or field.data <= 0:
        raise ValidationError("Amount must be a positive number")

    
def validate_email_or_phone(self, field):
        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        phone_pattern = r"^\+?\d{10,15}$"
        if not re.match(email_pattern, field.data) and not re.match(phone_pattern, field.data):
            raise ValidationError("Enter a valid email or phone number")

#Form
class RegistrationForm(FF):
    full_name=StringField('Full Name',validators=[DataRequired(),name_val])  #mathi bata taneko
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    phone_num=StringField('Phone Number',validators=[DataRequired(),number_val])
    address=StringField('Address',validators=[DataRequired()])
    password=PasswordField('Password',validators=[DataRequired(),pw_val])
    confirm_pw=PasswordField('Confirm Password',validators=[DataRequired(),EqualTo('password')])
    acc_type=SelectField('Choose your Account Type',choices=[('personal','Personal Finance Management'),('shop','Business / Shop Management')],validators=[DataRequired()])
    submit=SubmitField('Register')

class LoginForm(FF):
    email_or_phone = StringField('Email or Phone', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

