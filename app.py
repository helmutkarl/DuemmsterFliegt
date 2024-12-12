import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, Round, Participant, Vote
from add_round import rounds_bp

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'votes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dein_geheimnis_schluessel'

db.init_app(app)
app.app_context().push()
db.create_all()

app.register_blueprint(rounds_bp)

ADMIN_PASSWORD = "feli"

def is_admin_logged_in():
    return session.get('admin_logged_in') == True

def get_current_round():
    return Round.query.order_by(Round.id.desc()).first()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    participants = Participant.query.all()
    current_r = get_current_round()
    current_round_name = current_r.name if current_r else "Keine Runde"
    return render_template('admin_dashboard.html', participants=participants, current_round_name=current_round_name)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash("Erfolgreich eingeloggt!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Falsches Passwort!", "danger")
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Ausgeloggt!", "info")
    return redirect(url_for('index'))

@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            if Participant.query.filter_by(name=name).first():
                flash("Spieler existiert bereits.", "warning")
            else:
                new_player = Participant(name=name)
                db.session.add(new_player)
                db.session.commit()
                flash("Spieler hinzugefügt!", "success")
            return redirect(url_for('add_player'))
    return render_template('add_player.html')

@app.route('/reset_votes')
def reset_votes():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    participants = Participant.query.all()
    for p in participants:
        p.votes = 0
    db.session.commit()
    flash("Stimmen zurückgesetzt!", "info")
    return redirect(url_for('admin_dashboard'))

@app.route('/player_vote', methods=['GET', 'POST'])
def player_vote():
    current_r = get_current_round()
    current_round_name = current_r.name if current_r else "Keine Runde"
    participants = Participant.query.all()

    # Prüfen ob bereits ein Spieler gewählt wurde
    voter_id = session.get('voter_id')
    if voter_id is not None:
        # Spieler bereits gewählt, direkt zum Abstimmungsformular
        step = 'cast_vote'
    else:
        # Noch kein Spieler gewählt, ggf. POST Anfrage auswerten
        step = 'select_player'
        if request.method == 'POST':
            if 'selected_player' in request.form:
                selected_player_id = request.form['selected_player']
                session['voter_id'] = selected_player_id
                step = 'cast_vote'
    
    return render_template('player_vote.html', step=step, participants=participants, current_round_name=current_round_name)

@app.route('/change_user')
def change_user():
    # Ermöglicht es den Benutzer zurückzusetzen
    session.pop('voter_id', None)
    flash("Benutzer zurückgesetzt. Wähle einen neuen Spieler aus.", "info")
    return redirect(url_for('player_vote'))

@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    voter_id = session.get('voter_id')
    voted_for_id = request.form.get('participant')
    current_r = get_current_round()

    if voter_id and voted_for_id and current_r:
        voter = Participant.query.get(int(voter_id))
        voted_for = Participant.query.get(int(voted_for_id))
        if voter and voted_for:
            new_vote = Vote(round_id=current_r.id, voter_id=voter.id, voted_for_id=voted_for.id)
            db.session.add(new_vote)
            voted_for.votes += 1
            db.session.commit()
            flash(f"Deine Stimme wurde für {voted_for.name} abgegeben!", "success")
        else:
            flash("Ungültige Auswahl", "danger")
    else:
        flash("Es ist ein Fehler beim Abstimmen aufgetreten!", "danger")

    return redirect(url_for('player_vote'))

@app.route('/get_game_data', methods=['GET'])
def get_game_data():
    participants = Participant.query.all()
    current_r = get_current_round()
    current_round_name = current_r.name if current_r else "Keine Runde"
    participants_data = [{'name': p.name, 'votes': p.votes} for p in participants]
    return jsonify({
        'round_name': current_round_name,
        'participants': participants_data
    })

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
