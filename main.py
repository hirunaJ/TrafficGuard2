from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a random secret key

# Configuring SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


login_manager = LoginManager(app)
login_manager.login_view = 'login'

offence_fines = {
    "Speeding": 150,
    "Running a Red Light": 200,
    "Illegal Parking": 75,
    "Driving Without a License": 500,
    "Seatbelt Violation": 50,
    "Using Mobile While Driving": 250,
    "Reckless Driving": 300,
    "Driving Under Influence (DUI)": 1000,
    "Expired Vehicle Registration": 100,
    "Failure to Yield": 150,
    "Driving Without Insurance": 400,
    "Wrong-Way Driving": 350
}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    

# Record Model
class Record(db.Model):
    __tablename__ = 'record'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    vehicle_number = db.Column(db.String(200), nullable=False)
    offense = db.Column(db.String(200), nullable=False)
    fine = db.Column(db.Integer, nullable=True)
    paid = db.Column(db.Boolean, default=False)
    license_number = db.Column(db.String(200), nullable=False)
    police_station = db.Column(db.String(200), nullable=False)
    officer_ref = db.Column(db.String(200), nullable=False)
    is_court_case = db.Column(db.Boolean, default=False)
    court_date = db.Column(db.DateTime, nullable=True)
    court = db.Column(db.String(200), nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Record {self.id}'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():

    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST','GET'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Try again.', 'danger')
    return render_template('index.html')

@app.route('/register', methods=['POST','GET'])
def register():

    username = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(username=username).first()
    if user:
        return render_template('index.html', error='Username already exists.')
    else:
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        session['username'] = username
        return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/about')
@login_required
def about():
    return render_template('about.html')

@app.route('/offence/create', methods=["POST","GET"])
@login_required
def createOffenceRecord():
    fname = request.form['fname']
    lname = request.form['lname']
    email = request.form['email']
    vehicle_number = request.form['vehicle_number']
    offense = request.form['offense']
    fine = offence_fines.get(offense, 0)
    paid = request.form.get('paid', 'false').lower() == 'true'
    license_number = request.form['license_number']
    police_station = request.form['police_station']
    officer_ref = request.form['officer_ref']
    is_court_case = request.form.get('is_court_case', 'false').lower() == 'true'
    court_date = request.form.get('court_date')
    court = request.form.get('court', '')

    # Convert court_date to datetime format if provided
    court_date = datetime.strptime(court_date, "%Y-%m-%d") if court_date else None

    # Create a new record instance
    new_task = Record(
        first_name=fname,
        last_name=lname,
        email=email,
        vehicle_number=vehicle_number,
        offense=offense,
        fine=int(fine) if fine else None,
        paid=paid,
        license_number=license_number,
        police_station=police_station,
        officer_ref=officer_ref,
        is_court_case=is_court_case,
        court_date=court_date,
        court=court
    )
    try:
        send_confirmation_email(email, new_task);
        db.session.add(new_task)
        db.session.commit()
        return redirect("/offence")
    except Exception as e:
        print(f"Error:{e}")
        return f'Error:{e}'
        
@app.route('/offence', methods=["POST","GET"])
@login_required
def offence():
    tasks = Record.query.all()
    return render_template('offence.html',tasks=tasks, offence_fines=offence_fines)


@app.route("/delete/<int:id>")
def delete(id):
    task_to_delete = Record.query.get_or_404(id)
    try:
        db.session.delete(task_to_delete)
        db.session.commit()  
        return redirect("/offence")
    except Exception as e:
        return f"Error:{e}"

@app.route("/update/<int:id>", methods=["GET","POST"])
def update(id):
    task = Record.query.get_or_404(id)
    if request.method == "POST":
        fname = request.form['fname']
        lname = request.form['lname']
        email = request.form['email']
        vehicle_number = request.form['vehicle_number']
        offense = request.form['offense']
        fine = offence_fines.get(offense, 0)
        paid = request.form.get('paid', 'false').lower() == 'true'
        license_number = request.form['license_number']
        police_station = request.form['police_station']
        officer_ref = request.form['officer_ref']
        is_court_case = request.form.get('is_court_case', 'false').lower() == 'true'
        court_date = request.form.get('court_date')
        court = request.form.get('court', '')
        task.first_name = fname
        task.last_name = lname
        task.email = email
        task.vehicle_number=vehicle_number
        task.offense=offense
        task.fine=int(fine) if fine else None
        task.paid=paid
        task.license_number=license_number
        task.police_station=police_station
        task.officer_ref=officer_ref
        task.is_court_case=is_court_case
        task.court_date=court_date
        task.court=court
        try:
            db.session.commit()
            return redirect("/offence")
        except Exception as e:
            print(f"ERROR:{e}")
            return "Error"
    else:
        return render_template("offence.html", task=task, offence_fines=offence_fines)
    

@app.route('/download_pdf/<int:id>')
def download_pdf(id):
    record = Record.query.get(id)
    if not record:
        return "Record not found", 404

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, height - 50, "Traffic Offense Report")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, height - 100, f"Record ID: {record.id}")
    pdf.drawString(50, height - 120, f"Name: {record.first_name} {record.last_name}")
    pdf.drawString(50, height - 140, f"Email: {record.email}")
    pdf.drawString(50, height - 160, f"Vehicle Number: {record.vehicle_number}")
    pdf.drawString(50, height - 180, f"Offense: {record.offense}")
    pdf.drawString(50, height - 200, f"Fine: ${record.fine if record.fine else 'N/A'}")
    pdf.drawString(50, height - 220, f"Paid: {'Yes' if record.paid else 'No'}")
    pdf.drawString(50, height - 240, f"License Number: {record.license_number}")
    pdf.drawString(50, height - 260, f"Police Station: {record.police_station}")
    pdf.drawString(50, height - 280, f"Officer Ref: {record.officer_ref}")
    pdf.drawString(50, height - 300, f"Court Case: {'Yes' if record.is_court_case else 'No'}")
    
    if record.is_court_case:
        pdf.drawString(50, height - 320, f"Court: {record.court}")
        pdf.drawString(50, height - 340, f"Court Date: {record.court_date.strftime('%Y-%m-%d') if record.court_date else 'N/A'}")

    pdf.drawString(50, height - 380, f"Date Created: {record.date_created.strftime('%Y-%m-%d')}")

    pdf.showPage()
    pdf.save()
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"record_{record.id}.pdf", mimetype="application/pdf")

def send_confirmation_email(email, record):
    message = Mail(
        from_email='trafficguard2@gmail.com',
        to_emails=email,
        subject='Traffic Offense Record Created',
        html_content=f'''
        <p>Hello {record.first_name} {record.last_name},</p>
        <p>Your traffic offense record has been successfully created.</p>
        <p><b>Vehicle Number:</b> {record.vehicle_number}</p>
        <p><b>Offense:</b> {record.offense}</p>
        <p><b>Fine:</b> ${record.fine if record.fine else 'N/A'}</p>
        <p><b>Paid:</b> {'Yes' if record.paid else 'No'}</p>
        <p>Best regards,<br>Your Traffic Management System</p>
        '''
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"✅ Email sent to {email}, Status Code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")

if __name__ in '__main__':
    # Create a db and table
    with app.app_context():
        db.create_all()
    app.run(debug=True)