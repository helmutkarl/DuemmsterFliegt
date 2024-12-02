from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///votes.db'
db = SQLAlchemy(app)

class Participant(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(80), unique=True, nullable=False)
	votes = db.Column(db.Integer, default=0)

@app.route('/')
def index():
	participants = Participant.query.all()
	return render_template('index.html', participants=participants)

@app.route('/vote', methods=['POST'])
def vote():
	voted_id = request.form['participant']
	participant = Participant.query.get(voted_id)
	if participant:
		participant.votes += 1
		db.session.commit()
	return redirect(url_for('index'))

@app.route('/add', methods=['GET', 'POST'])
def add():
	if request.method == 'POST':
		name = request.form['name']
		if name:
			new_participant = Participant(name=name)
			db.session.add(new_participant)
			db.session.commit()
		return redirect(url_for('index'))
	return render_template('add.html')

@app.route('/reset')
def reset():
	db.session.query(Participant).update({Participant.votes: 0})
	db.session.commit()
	return redirect(url_for('index'))

if __name__ == '__main__':
	with app.app_context():
		db.create_all()
	app.run(host='0.0.0.0', port=5000)
