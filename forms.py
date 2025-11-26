from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, FloatField, DateField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional
from datetime import date

# Static choices for categories and emotions - can be fetched from app.py or config later
# For now, keep them here for simplicity or pass them during form instantiation.
# These are the same as in your app.py's static lists.
category_choices = [
    ("Groceries", "Groceries"), ("Transport", "Transport"), ("Entertainment", "Entertainment"),
    ("Utilities", "Utilities"), ("Dining", "Dining"), ("Shopping", "Shopping"),
    ("Health", "Health"), ("Travel", "Travel"), ("Education", "Education"),
    ("Savings Goal", "Savings Goal"), ("Other", "Other")
]
emotion_choices = [
    ("", "-- Select Emotion --"), ("happy", "😊 Happy"), ("neutral", "😐 Neutral"),
    ("sad", "😟 Sad"), ("stressed", "😠 Stressed"), ("excited", "🎉 Excited"),
    ("regretful", "🤦 Regretful"), ("necessary", "✅ Necessary"), ("motivated", "💪 Motivated")
]

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=60)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class ExpenseForm(FlaskForm):
    amount = FloatField('Amount (₹)', validators=[DataRequired(), NumberRange(min=0.01)])
    category = SelectField('Category', choices=category_choices, validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired(), Length(min=1, max=200)])
    merchant = StringField('Merchant (Optional)', validators=[Optional(), Length(max=100)])
    date = DateField('Date', validators=[DataRequired()], default=date.today, format='%Y-%m-%d')
    emotion_tag = SelectField('Emotion (Optional)', choices=emotion_choices, validators=[Optional()])
    submit = SubmitField('Log Expense')

# You can add BudgetForm and GoalForm here later in a similar fashion
# class BudgetForm(FlaskForm):
#     category = SelectField('Category', choices=[("Overall", "Overall")] + category_choices, validators=[DataRequired()])
#     amount = FloatField('Amount (₹)', validators=[DataRequired(), NumberRange(min=0)])
#     # Month and Year can be split or use a MonthField if available/custom
#     month = SelectField('Month', choices=[(str(m), date(2000, m, 1).strftime('%B')) for m in range(1, 13)], validators=[DataRequired()])
#     year = SelectField('Year', choices=[(str(y), str(y)) for y in range(date.today().year - 5, date.today().year + 5)], default=str(date.today().year), validators=[DataRequired()])
#     submit = SubmitField('Set/Update Budget')

# class GoalForm(FlaskForm):
#     name = StringField('Goal Name', validators=[DataRequired(), Length(max=150)])
#     target_amount = FloatField('Target Amount (₹)', validators=[DataRequired(), NumberRange(min=0.01)])
#     current_amount = FloatField('Current Amount Saved (₹) (Optional)', validators=[Optional(), NumberRange(min=0)])
#     due_date = DateField('Target Date (Optional)', validators=[Optional()], format='%Y-%m-%d')
#     submit = SubmitField('Set Goal')