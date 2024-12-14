import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, Round, Participant, Vote, GameSetting
from add_round import rounds_bp
from sqlalchemy import distinct

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'votes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dein_geheimnis_schluessel'

db.init_app(app)
app.app_context().push()
db.create_all()

# Falls kein GameSetting existiert, erstellen
if not GameSetting.query.first():
    setting = GameSetting(start_hearts=3, lose_count=1)
    db.session.add(setting)
    db.session.commit()

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
    setting = GameSetting.query.first()

    active_participants = Participant.query.filter(Participant.hearts > 0).all()
    total_active = len(active_participants)

    votes_this_round = []
    votes_count = 0
    if current_r:
        votes_this_round = Vote.query.filter_by(round_id=current_r.id).all()
        votes_count = db.session.query(distinct(Vote.voter_id)).filter(Vote.round_id == current_r.id).count()

    return render_template('admin_dashboard.html',
                           participants=participants,
                           current_round_name=current_round_name,
                           setting=setting,
                           total_active=total_active,
                           votes_count=votes_count,
                           votes_this_round=votes_this_round)

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
                setting = GameSetting.query.first()
                new_player = Participant(name=name, hearts=setting.start_hearts)
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

@app.route('/new_game', methods=['GET', 'POST'])
def new_game():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        start_hearts = int(request.form.get('start_hearts', 3))
        lose_count = int(request.form.get('lose_count', 1))
        setting = GameSetting.query.first()
        if not setting:
            setting = GameSetting(start_hearts=start_hearts, lose_count=lose_count)
            db.session.add(setting)
        else:
            setting.start_hearts = start_hearts
            setting.lose_count = lose_count

        participants = Participant.query.all()
        for p in participants:
            p.hearts = start_hearts
            p.votes = 0
        db.session.commit()

        # Votes löschen
        Vote.query.delete()
        db.session.commit()

        # Runden löschen
        Round.query.delete()
        db.session.commit()

        flash("Neues Spiel gestartet! Alle Spielerherzen, Stimmen und Runden wurden zurückgesetzt.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('new_game.html')

@app.route('/player_vote', methods=['GET', 'POST'])
def player_vote():
    current_r = get_current_round()
    current_round_name = current_r.name if current_r else "Keine Runde"
    active_participants = Participant.query.filter(Participant.hearts > 0).all()

    voter_id = session.get('voter_id')
    current_player = Participant.query.get(voter_id) if voter_id else None

    if current_player and current_player.hearts == 0:
        flash("Du hast keine Herzen mehr und kannst nicht mehr abstimmen!", "danger")
        current_player = None
        session.pop('voter_id', None)

    if current_player is not None:
        step = 'cast_vote'
    else:
        step = 'select_player'
        if request.method == 'POST':
            if 'selected_player' in request.form:
                selected_player_id = request.form['selected_player']
                selected_p = Participant.query.get(int(selected_player_id))
                if selected_p and selected_p.hearts > 0:
                    session['voter_id'] = selected_player_id
                    current_player = selected_p
                    step = 'cast_vote'
                else:
                    flash("Dieser Spieler kann nicht mehr wählen, da er 0 Herzen hat.", "danger")
                    step = 'select_player'

    return render_template('player_vote.html', step=step, participants=active_participants, current_round_name=current_round_name, current_player=current_player)

@app.route('/change_user')
def change_user():
    session.pop('voter_id', None)
    flash("Benutzer zurückgesetzt. Wähle einen neuen Spieler aus.", "info")
    return redirect(url_for('player_vote'))

@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    voter_id = session.get('voter_id')
    voted_for_id = request.form.get('participant')
    current_r = get_current_round()

    if not current_r:
        flash("Es ist derzeit keine Runde aktiv, du kannst nicht abstimmen!", "danger")
        return redirect(url_for('player_vote'))

    voter = Participant.query.get(int(voter_id)) if voter_id else None
    if voter is not None and voter.hearts == 0:
        flash("Du hast keine Herzen mehr und kannst nicht mehr abstimmen!", "danger")
        return redirect(url_for('player_vote'))

    # Prüfen, ob der Wähler bereits in dieser Runde abgestimmt hat
    already_voted = Vote.query.filter_by(round_id=current_r.id, voter_id=voter_id).first()
    if already_voted:
        flash("Du hast in dieser Runde bereits abgestimmt!", "warning")
        return redirect(url_for('player_vote'))

    if voter_id and voted_for_id and current_r:
        voted_for = Participant.query.get(int(voted_for_id))
        if voted_for and voted_for.hearts > 0 and voter and voter.hearts > 0:
            new_vote = Vote(round_id=current_r.id, voter_id=voter.id, voted_for_id=voted_for.id)
            db.session.add(new_vote)
            voted_for.votes += 1
            db.session.commit()
            flash(f"Deine Stimme wurde für {voted_for.name} abgegeben!", "success")
        else:
            flash("Ungültige Auswahl oder Spieler kann nicht mehr gewählt werden.", "danger")
    else:
        flash("Es ist derzeit keine Runde aktiv, du kannst nicht abstimmen!", "danger")

    return redirect(url_for('player_vote'))


@app.route('/get_game_data', methods=['GET'])
def get_game_data():
    participants = Participant.query.all()
    current_r = get_current_round()
    current_round_name = current_r.name if current_r else "Keine Runde"
    participants_data = [{'id': p.id, 'name': p.name, 'votes': p.votes, 'hearts': p.hearts} for p in participants]
    return jsonify({
        'round_name': current_round_name,
        'participants': participants_data
    })

@app.route('/get_current_votes', methods=['GET'])
def get_current_votes():
    current_r = get_current_round()
    if not current_r:
        return jsonify({'votes': [], 'votes_count': 0, 'total_active': 0})

    votes = Vote.query.filter_by(round_id=current_r.id).all()
    votes_list = []
    for v in votes:
        votes_list.append({
            'voter': v.voter.name,
            'voted_for': v.voted_for.name
        })
    active_participants = Participant.query.filter(Participant.hearts > 0).all()
    total_active = len(active_participants)
    votes_count = db.session.query(distinct(Vote.voter_id)).filter(Vote.round_id == current_r.id).count()

    return jsonify({
        'votes': votes_list,
        'votes_count': votes_count,
        'total_active': total_active
    })

@app.route('/delete_player/<int:player_id>', methods=['POST'])
def delete_player(player_id):
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    player = Participant.query.get(player_id)
    if player:
        # Entferne auch alle Votes, in denen dieser Spieler vorkommt
        # Alternativ einfach löschen (durch cascade?), aber hier machen wir es manuell:
        Vote.query.filter((Vote.voter_id == player_id) | (Vote.voted_for_id == player_id)).delete()
        db.session.delete(player)
        db.session.commit()
        flash(f"Spieler {player.name} entfernt.", "info")
    else:
        flash("Spieler wurde nicht gefunden.", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_all_data', methods=['POST'])
def delete_all_data():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    # Komplett DB neu erstellen
    db.drop_all()
    db.create_all()

    # Erneut die Standard-GameSettings hinzufügen
    setting = GameSetting(start_hearts=3, lose_count=1)
    db.session.add(setting)
    db.session.commit()

    flash("Alle Daten wurden gelöscht und die DB neu erstellt!", "warning")
    return redirect(url_for('admin_dashboard'))

@app.route('/adjust_hearts/<int:player_id>', methods=['POST'])
def adjust_hearts(player_id):
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    player = Participant.query.get(player_id)
    if not player:
        flash("Spieler nicht gefunden.", "danger")
        return redirect(url_for('admin_dashboard'))

    action = request.args.get('action', '')
    if action == 'add':
        player.hearts += 1
        db.session.commit()
        flash(f"Spieler {player.name} hat nun {player.hearts} Herzen (+1).", "success")
    elif action == 'sub':
        if player.hearts > 0:
            player.hearts -= 1
            db.session.commit()
            flash(f"Spieler {player.name} hat nun {player.hearts} Herzen (-1).", "warning")
        else:
            flash(f"Spieler {player.name} hat bereits 0 Herzen, kann nicht weiter reduziert werden.", "danger")
    else:
        flash("Ungültige Aktion.", "danger")

    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
