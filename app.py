
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
import datetime
from collections import defaultdict
import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from forms import RegistrationForm, LoginForm, ExpenseForm # <--- IMPORT YOUR FORMS

# Initialize Flask App
app = Flask(__name__)

# --- Configuration ---
# Define basedir first, before it's used in app.config
basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-key')  # Use secure key in production
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///expenses.db') # Use environment variable or fallback to SQLite
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to 'login' route if @login_required fails
login_manager.login_message_category = "info" # For flash messages

# --- Database Models ---
class User(UserMixin, db.Model): # UserMixin provides is_authenticated, is_active, etc.
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # Increased length for hash

    expenses = db.relationship('Expense', backref='user', lazy=True, cascade="all, delete-orphan")
    budgets = db.relationship('Budget', backref='user', lazy=True, cascade="all, delete-orphan")
    goals = db.relationship('Goal', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    merchant = db.Column(db.String(100), nullable=True)
    emotion_tag = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # No default, set by current_user
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def as_dict(self):
       data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
       if isinstance(data.get('date'), datetime.date): data['date'] = data['date'].isoformat()
       if isinstance(data.get('created_at'), datetime.datetime): data['created_at'] = data['created_at'].isoformat()
       return data

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'category', 'month', 'year', name='_user_category_month_year_uc'),)

    def as_dict(self):
       return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    due_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def as_dict(self):
       data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
       if isinstance(data.get('due_date'), datetime.date): data['due_date'] = data['due_date'].isoformat()
       if isinstance(data.get('created_at'), datetime.datetime): data['created_at'] = data['created_at'].isoformat()
       return data

# --- Create Tables at Startup ---
@app.route('/init-db')
def init_db():
    db.create_all()
    return "Tables created!"

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Static Data ---
# Renamed to avoid conflict with potential form fields if they were named categories_db
categories_db_static_list = ["Groceries", "Transport", "Entertainment", "Utilities", "Dining", "Shopping", "Health", "Travel", "Education", "Savings Goal", "Other"]
merchants_db_static_list = ["Big Bazaar", "Uber", "INOX", "BSES", "Swiggy", "Amazon", "Apollo Pharmacy", "Starbucks", "Udemy", "Self/Bank", "Local Market"]

# --- Helper Functions (parse_expense_text remains largely the same) ---
def parse_expense_text(text):
    amount = None; category = None; merchant = None; description = text
    words = text.lower().split()
    for i, word in enumerate(words):
        cleaned_word = ''.join(filter(lambda x: x.isdigit() or x == '.', word))
        if cleaned_word and (cleaned_word.replace('.', '', 1).isdigit() and cleaned_word.count('.') < 2):
            try: amount = float(cleaned_word); words.pop(i); text = " ".join(words); break
            except ValueError: pass
    remaining_text_lower = text.lower()
    if not category:
        for cat_option in categories_db_static_list:
            if cat_option.lower() in remaining_text_lower: category = cat_option; break
    if not merchant:
        sorted_merchants = sorted(merchants_db_static_list, key=len, reverse=True)
        for merch_option in sorted_merchants:
            if merch_option.lower() in remaining_text_lower: merchant = merch_option; break
    if amount:
        if category and merchant: description = f"{category} at {merchant}"
        elif category: description = f"{category} expense"
        elif merchant: description = f"Spent at {merchant}"
        else: description = f"Expense of {amount}"
    return {"amount": amount, "category": category, "merchant": merchant, "description": description, "date": datetime.date.today()}

# --- Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user_email = User.query.filter_by(email=form.email.data).first()
        if existing_user_email:
            flash('Email address already registered.', 'warning')
            return redirect(url_for('register'))
        
        existing_user_username = User.query.filter_by(username=form.username.data).first()
        if existing_user_username:
            flash('Username already taken.', 'warning')
            return redirect(url_for('register'))

        new_user = User(username=form.username.data, email=form.email.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Application Routes ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        latest_expenses_query = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc(), Expense.id.desc()).limit(5).all()
        return render_template('index.html', expenses=latest_expenses_query)
    return render_template('index.html') 

# Page to display both smart log input and the WTForm for manual expense logging
@app.route('/add_expense_page', methods=['GET'])
@login_required
def add_expense_page():
    form = ExpenseForm()
    # Dynamically set choices for category and emotion from app.py static lists
    # This ensures consistency if app.py lists change
    form.category.choices = [(c, c) for c in categories_db_static_list]
    # emotion_choices from forms.py already includes the empty option, so just pass it
    # form.emotion_tag.choices = emotion_choices # This is already handled by forms.py directly

    return render_template('add_expense.html', 
                           manual_form=form, # Pass the WTForm as manual_form
                           categories=categories_db_static_list, # Still needed for smart log parsing info maybe
                           merchants=merchants_db_static_list)

# Endpoint for WTForm based manual expense submission
@app.route('/add_expense_submit', methods=['POST'])
@login_required
def add_expense_submit():
    form = ExpenseForm()
    # Ensure choices are set for validation on POST request as well
    form.category.choices = [(c, c) for c in categories_db_static_list]

    if form.validate_on_submit():
        new_expense = Expense(
            amount=form.amount.data,
            category=form.category.data,
            description=form.description.data,
            merchant=form.merchant.data,
            date=form.date.data,
            emotion_tag=form.emotion_tag.data if form.emotion_tag.data else None,
            user_id=current_user.id
        )
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense logged successfully via form!', 'success')
        return redirect(url_for('add_expense_page')) # Redirect back to clear form
    else:
        # If form validation fails, re-render the page with the form and errors
        flash('Error in form submission. Please check the fields.', 'danger')
        return render_template('add_expense.html', manual_form=form, categories=categories_db_static_list, merchants=merchants_db_static_list)


# Endpoint for JSON based expense logging (primarily for Smart Log JS)
@app.route('/log_expense_json', methods=['POST']) # Renamed to avoid confusion with WTForm POST
@login_required
def log_expense_json():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400
        
    parsed_data = {}
    text_input = data.get('text_input')

    if text_input:
        parsed_data = parse_expense_text(text_input)
        if not parsed_data.get('amount'):
            return jsonify({"error": "Could not parse amount from text."}), 400
        
        parsed_data['amount'] = float(data.get('amount', parsed_data.get('amount')))
        parsed_data['category'] = data.get('category') or parsed_data.get('category')
        parsed_data['description'] = data.get('description') or parsed_data.get('description')
        parsed_data['merchant'] = data.get('merchant') or parsed_data.get('merchant')
        date_str = data.get('date')
        parsed_data['date'] = datetime.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else parsed_data.get('date', datetime.date.today())
        parsed_data['emotion_tag'] = data.get('emotion_tag')

        if not parsed_data.get('category'):
            parsed_data['category'] = "Other"
        if not parsed_data.get('description'):
            parsed_data['description'] = f"{parsed_data['category']} expense"

        new_expense = Expense(
            amount=parsed_data['amount'], category=parsed_data['category'],
            description=parsed_data['description'], date=parsed_data['date'],
            merchant=parsed_data.get('merchant'), emotion_tag=parsed_data.get('emotion_tag'),
            user_id=current_user.id
        )
        db.session.add(new_expense)
        db.session.commit()
        return jsonify({"message": "Smart expense logged successfully!", "expense": new_expense.as_dict()}), 201
    else:
        return jsonify({"error": "text_input not provided for smart logging OR this endpoint is for JSON only."}), 400


@app.route('/dashboard')
@login_required
def dashboard(): return render_template('dashboard.html')

@app.route('/api/spending_by_category')
@login_required
def spending_by_category_api():
    category_spending = db.session.query(Expense.category, db.func.sum(Expense.amount))\
        .filter_by(user_id=current_user.id).group_by(Expense.category).all()
    labels = [item[0] for item in category_spending]
    data_values = [float(item[1]) for item in category_spending]
    return jsonify({"labels": labels, "data": data_values})

@app.route('/api/spending_over_time')
@login_required
def spending_over_time_api():
    user_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.asc()).all()
    if not user_expenses: return jsonify({"labels": [], "data": []})
    monthly_spending = defaultdict(float)
    first_expense_date = user_expenses[0].date; last_expense_date = user_expenses[-1].date
    for expense in user_expenses:
        month_year_key = expense.date.strftime("%Y-%m")
        monthly_spending[month_year_key] += expense.amount
    labels = []; data_values = []
    current_loop_date = datetime.date(first_expense_date.year, first_expense_date.month, 1)
    while current_loop_date <= last_expense_date:
        labels.append(current_loop_date.strftime("%b %Y"))
        data_values.append(monthly_spending.get(current_loop_date.strftime("%Y-%m"), 0))
        if current_loop_date.month == 12: current_loop_date = datetime.date(current_loop_date.year + 1, 1, 1)
        else: current_loop_date = datetime.date(current_loop_date.year, current_loop_date.month + 1, 1)
    return jsonify({"labels": labels, "data": data_values})

@app.route('/api/emotion_spending')
@login_required
def emotion_spending_api():
    emotion_summary_query = db.session.query(Expense.emotion_tag, db.func.sum(Expense.amount))\
        .filter(Expense.user_id == current_user.id, Expense.emotion_tag != None).group_by(Expense.emotion_tag).all()
    labels = [item[0] for item in emotion_summary_query]
    data_values = [float(item[1]) for item in emotion_summary_query]
    return jsonify({"labels": labels, "data": data_values})

@app.route('/budget_page')
@login_required
def budget_page():
    now = datetime.datetime.now()
    current_view_month = request.args.get('month', default=now.month, type=int)
    current_view_year = request.args.get('year', default=now.year, type=int)
    return render_template('budget.html', categories=categories_db_static_list, 
                           view_month=current_view_month, view_year=current_view_year)

@app.route('/set_budget', methods=['POST']) # This is an API endpoint, keep as JSON
@login_required
def set_budget():
    data = request.json; category = data.get('category'); amount = float(data.get('amount'))
    month = int(data.get('month')); year = int(data.get('year'))
    if not category or amount < 0 or not (1 <= month <= 12) or year < 2000:
        return jsonify({"error": "Invalid budget data"}), 400
    existing_budget = Budget.query.filter_by(user_id=current_user.id, category=category, month=month, year=year).first()
    if existing_budget: existing_budget.amount = amount; message = "Budget updated!"
    else: new_budget = Budget(user_id=current_user.id, category=category, amount=amount, month=month, year=year); db.session.add(new_budget); message = "Budget set!"
    db.session.commit()
    budget_entry = existing_budget or new_budget
    return jsonify({"message": message, "budget": budget_entry.as_dict()}), 201

@app.route('/api/budget_status')
@login_required
def budget_status_api():
    now = datetime.datetime.now()
    target_month = request.args.get('month', default=now.month, type=int)
    target_year = request.args.get('year', default=now.year, type=int)
    user_budgets = Budget.query.filter_by(user_id=current_user.id, month=target_month, year=target_year).all()
    status_list = []
    for budget in user_budgets:
        query = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id, 
            db.extract('month', Expense.date) == target_month,
            db.extract('year', Expense.date) == target_year)
        if budget.category != "Overall": query = query.filter(Expense.category == budget.category)
        current_spending = float(query.scalar() or 0.0)
        remaining_budget = budget.amount - current_spending; forecast = 0; on_track = True
        if target_month == now.month and target_year == now.year:
            days_in_month_obj = datetime.date(target_year, target_month + 1, 1) - datetime.timedelta(days=1) if target_month < 12 else datetime.date(target_year, 12, 31)
            days_in_month = days_in_month_obj.day; days_passed = now.day
            days_left = days_in_month - days_passed if days_passed <= days_in_month else 0
            if days_passed > 0 and budget.amount >= 0:
                daily_avg_spending = current_spending / days_passed
                forecast = current_spending + (daily_avg_spending * days_left if days_left > 0 else 0)
            elif budget.amount == 0: forecast = current_spending
            on_track = forecast <= budget.amount if forecast > 0 and budget.amount > 0 else (current_spending <= budget.amount)
        else: forecast = current_spending; on_track = current_spending <= budget.amount
        status_list.append({
            "category": budget.category, "budget_amount": budget.amount, "spent": current_spending,
            "remaining": remaining_budget, "forecasted_spending": forecast, "on_track": on_track,
            "month": target_month, "year": target_year})
    return jsonify(status_list)

@app.route('/goals_page')
@login_required
def goals_page(): return render_template('goals.html')

@app.route('/set_goal', methods=['POST']) # This is an API endpoint, keep as JSON
@login_required
def set_goal():
    data = request.json; name = data.get('name'); target_amount_str = data.get('target_amount')
    current_amount_str = data.get('current_amount', '0.0'); due_date_str = data.get('due_date')
    if not name or not target_amount_str: return jsonify({"error": "Goal name and target amount are required."}), 400
    try:
        target_amount = float(target_amount_str); current_amount = float(current_amount_str)
        if target_amount <= 0: raise ValueError("Target amount must be positive.")
        if current_amount < 0: raise ValueError("Current amount cannot be negative.")
    except ValueError as e: return jsonify({"error": f"Invalid amount: {e}"}), 400
    due_date = None
    if due_date_str:
        try: due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError: return jsonify({"error": "Invalid due date format."}), 400
    new_goal = Goal(user_id=current_user.id, name=name, target_amount=target_amount, current_amount=current_amount, due_date=due_date)
    db.session.add(new_goal); db.session.commit()
    return jsonify({"message": "Goal set successfully!", "goal": new_goal.as_dict()}), 201

@app.route('/contribute_to_goal/<int:goal_id>', methods=['POST']) # API endpoint
@login_required
def contribute_to_goal(goal_id):
    data = request.json; amount_str = data.get('amount')
    if not amount_str: return jsonify({"error": "Contribution amount required."}), 400
    try:
        amount = float(amount_str)
        if amount <= 0: raise ValueError("Contribution must be positive.")
    except ValueError as e: return jsonify({"error": f"Invalid amount: {e}"}), 400
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404() 
    goal.current_amount += amount
    contribution_expense = Expense(user_id=current_user.id, amount=amount, category="Savings Goal", description=f"Contribution to goal: {goal.name}", date=datetime.date.today(), merchant="Self/Bank", emotion_tag="motivated")
    db.session.add(contribution_expense); db.session.commit()
    return jsonify({"message": f"Contributed {amount:.2f} to {goal.name}", "goal": goal.as_dict()})

@app.route('/api/goals')
@login_required
def get_goals_api():
    user_goals_query = Goal.query.filter_by(user_id=current_user.id).all() 
    return jsonify([goal.as_dict() for goal in user_goals_query])

@app.route('/timeline_page')
@login_required
def timeline_page(): return render_template('timeline.html')

@app.route('/api/expenses_timeline')
@login_required
def expenses_timeline_api():
    page = request.args.get('page', 1, type=int); per_page = request.args.get('per_page', 10, type=int)
    pagination = Expense.query.filter_by(user_id=current_user.id)\
        .order_by(Expense.date.desc(), Expense.id.desc())\
        .paginate(page=page, per_page=per_page, error_out=False) 
    expenses_on_page = [exp.as_dict() for exp in pagination.items]
    return jsonify({
        "expenses": expenses_on_page, "total_items": pagination.total, "current_page": pagination.page,
        "per_page": pagination.per_page, "total_pages": pagination.pages,
        "has_next": pagination.has_next, "has_prev": pagination.has_prev })


# if __name__ == '__main__':
#     # Remember to run Flask-Migrate commands from your terminal:
#     # flask db init (first time only)
#     # flask db migrate -m "Initial migration"
#     # flask db upgrade
#     app.run(debug=True)