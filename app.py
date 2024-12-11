from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///votes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dein_geheimnis_schluessel'  # Ersetze dies durch einen sicheren Schlüssel
db = SQLAlchemy(app)

# **Definiere zuerst die Modelle**
class Round(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    votes = db.Column(db.Integer, default=0)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey('round.id'), nullable=False)
    voter_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    voted_for_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    voter = db.relationship('Participant', foreign_keys=[voter_id], backref='voted_votes')
    voted_for = db.relationship('Participant', foreign_keys=[voted_for_id], backref='received_votes')
    round = db.relationship('Round', backref='votes')

# **Datenbank bei jedem Start neu erstellen**
with app.app_context():
    db.drop_all()
    db.create_all()
    if not Round.query.first():
        initial_round = Round(name="Round 1", active=True)
        db.session.add(initial_round)
        db.session.commit()

# Route für die Startseite
@app.route('/')
def index():
    current_round = Round.query.filter_by(active=True).first()
    return render_template('index.html', current_round=current_round)

# Route für das Admin-Dashboard
@app.route('/admin')
def admin_dashboard():
    participants = Participant.query.all()
    current_round = Round.query.filter_by(active=True).first()
    if current_round:
        votes = Vote.query.filter_by(round_id=current_round.id).all()
    else:
        votes = []
    return render_template('admin_dashboard.html', participants=participants, votes=votes, current_round=current_round)

# Route zum Hinzufügen von Spielern (Admin)
@app.route('/admin/add_player', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        name = request.form['name']
        if not name:
            flash('Name darf nicht leer sein.', 'warning')
            return redirect(url_for('add_player'))
        if Participant.query.filter_by(name=name).first():
            flash('Spieler mit diesem Namen existiert bereits.', 'warning')
            return redirect(url_for('add_player'))
        new_player = Participant(name=name)
        db.session.add(new_player)
        db.session.commit()
        flash(f'Spieler {name} hinzugefügt.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_player.html')

# Route zum Entfernen von Spielern (Admin)
@app.route('/admin/remove_player/<int:player_id>', methods=['POST'])
def remove_player(player_id):
    player = Participant.query.get(player_id)
    if player:
        # Entferne alle zugehörigen Stimmen
        Vote.query.filter((Vote.voter_id == player_id) | (Vote.voted_for_id == player_id)).delete()
        db.session.delete(player)
        db.session.commit()
        flash(f'Spieler {player.name} entfernt.', 'success')
    else:
        flash('Spieler nicht gefunden.', 'danger')
    return redirect(url_for('admin_dashboard'))

# Route zum Zurücksetzen der Stimmen (Admin)
@app.route('/admin/reset_votes')
def reset_votes():
    # Setze alle Stimmen zurück
    Participant.query.update({Participant.votes: 0})
    # Lösche alle bisherigen Abstimmungen
    Vote.query.delete()
    db.session.commit()
    flash('Alle Stimmen wurden zurückgesetzt.', 'success')
    return redirect(url_for('admin_dashboard'))

# Route zum Hinzufügen einer neuen Runde (Admin)
@app.route('/admin/add_round', methods=['GET', 'POST'])
def add_round():
    if request.method == 'POST':
        # Automatisch den Rundenname hochzählen
        last_round = Round.query.order_by(Round.id.desc()).first()
        next_round_number = last_round.id + 1 if last_round else 1
        name = f"Round {next_round_number}"
        # Deaktiviere alle bisherigen Runden
        Round.query.update({Round.active: False})
        # Setze alle Stimmen auf 0
        Participant.query.update({Participant.votes: 0})
        # Lösche alle bisherigen Abstimmungen
        Vote.query.delete()
        # Starte die neue Runde
        new_round = Round(name=name, active=True)
        db.session.add(new_round)
        db.session.commit()
        flash(f'Neue Runde "{name}" gestartet und Stimmen wurden zurückgesetzt.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_round.html')

# Route für die Spielerauswahl und Abstimmung
@app.route('/vote', methods=['GET', 'POST'])
def player_vote():
    current_round = Round.query.filter_by(active=True).first()
    if not current_round:
        flash('Keine aktive Runde. Bitte warte auf den Admin, um eine neue Runde zu starten.', 'warning')
        return redirect(url_for('index'))
    
    if 'player_id' in session:
        player_id = session['player_id']
        last_voted_round_id = session.get('last_voted_round_id')
        if last_voted_round_id != current_round.id:
            # Spieler kann in der neuen Runde abstimmen
            return redirect(url_for('cast_vote'))
        else:
            # Spieler hat bereits abgestimmt
            flash('Du hast bereits abgestimmt.', 'info')
            return render_template('player_vote.html', step='already_voted', current_round=current_round)
    
    if request.method == 'POST':
        # Spieler wählt seine Identität
        selected_player_id = request.form.get('selected_player')
        if not selected_player_id:
            flash('Bitte wähle deinen Spielernamen aus.', 'warning')
            return redirect(url_for('player_vote'))
        session['player_id'] = int(selected_player_id)
        # Überprüfe, ob der Spieler bereits in dieser Runde abgestimmt hat
        vote = Vote.query.filter_by(round_id=current_round.id, voter_id=int(selected_player_id)).first()
        if not vote:
            # Spieler hat noch nicht abgestimmt
            return redirect(url_for('cast_vote'))
        else:
            # Spieler hat bereits abgestimmt
            session['last_voted_round_id'] = current_round.id
            flash('Du hast bereits abgestimmt.', 'info')
            return render_template('player_vote.html', step='already_voted', current_round=current_round)
    
    participants = Participant.query.all()
    return render_template('player_vote.html', participants=participants, step='select_player', current_round=current_round)

# Route zum Abstimmen
@app.route('/cast_vote', methods=['GET', 'POST'])
def cast_vote():
    current_round = Round.query.filter_by(active=True).first()
    if not current_round:
        flash('Keine aktive Runde. Bitte warte auf den Admin, um eine neue Runde zu starten.', 'warning')
        return redirect(url_for('index'))
    
    if 'player_id' not in session:
        flash('Bitte wähle zuerst deinen Spielernamen aus.', 'warning')
        return redirect(url_for('player_vote'))
    
    player_id = session['player_id']
    # Überprüfe, ob der Spieler bereits abgestimmt hat
    existing_vote = Vote.query.filter_by(round_id=current_round.id, voter_id=player_id).first()
    if existing_vote:
        flash('Du hast bereits abgestimmt.', 'info')
        # Set 'last_voted_round_id' in session
        session['last_voted_round_id'] = current_round.id
        return redirect(url_for('player_vote'))
    
    participants = Participant.query.all()  # Ermöglicht Selbstabstimmung
    
    if request.method == 'POST':
        voted_for_id = request.form.get('participant')
        if not voted_for_id:
            flash('Bitte wähle einen Teilnehmer aus.', 'warning')
            return redirect(url_for('cast_vote'))
        voted_for = Participant.query.get(voted_for_id)
        if voted_for:
            # Stimme hinzufügen
            voted_for.votes += 1
            vote = Vote(round_id=current_round.id, voter_id=player_id, voted_for_id=voted_for_id)
            db.session.add(vote)
            db.session.commit()
            flash(f'Du hast für {voted_for.name} abgestimmt.', 'success')
            # Set 'last_voted_round_id' in session
            session['last_voted_round_id'] = current_round.id
            return redirect(url_for('player_vote'))
        else:
            flash('Ausgewählter Teilnehmer existiert nicht.', 'danger')
            return redirect(url_for('cast_vote'))
    
    # Ermitteln des aktuellen Spielers
    current_player = Participant.query.get(player_id)
    
    return render_template('player_vote.html', participants=participants, step='cast_vote', current_player=current_player, current_round=current_round)

# Route für das Logout (Spieler)
@app.route('/logout')
def logout():
    session.pop('player_id', None)
    session.pop('last_voted_round_id', None)
    flash('Du hast deine Identität zurückgesetzt.', 'success')
    return redirect(url_for('player_vote'))

# **Neue Route zur Abfrage der aktuellen Runde**
@app.route('/current_round')
def current_round_route():
    current_round = Round.query.filter_by(active=True).first()
    if current_round:
        return jsonify({
            'id': current_round.id,
            'name': current_round.name
        })
    else:
        return jsonify({
            'id': None,
            'name': None
        })

@app.route('/get_participants_data', methods=['GET'])
def get_participants_data():
    participants = Participant.query.all()
    participants_data = [
        {'name': p.name, 'votes': p.votes} for p in participants
    ]
    return jsonify(participants_data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
