from flask import Blueprint, flash, redirect, url_for, session
from models import db, Round, Participant, GameSetting

rounds_bp = Blueprint('rounds', __name__)

def is_admin_logged_in():
    return session.get('admin_logged_in') == True

def get_current_round():
    return Round.query.order_by(Round.id.desc()).first()

def apply_round_end_logic():
    setting = GameSetting.query.first()
    if not setting:
        setting = GameSetting(start_hearts=3, lose_count=1)
        db.session.add(setting)
        db.session.commit()
        
    participants = Participant.query.order_by(Participant.votes.desc()).all()
    current_round = get_current_round()

    if current_round:
        if len(participants) > 0:
            top_votes = participants[0].votes
            # Finde alle Spieler mit top_votes
            top_players = [p for p in participants if p.votes == top_votes]

            # Alle Top-Spieler verlieren ein Herz
            for p in top_players:
                if p.hearts > 0:
                    p.hearts -= 1

        # Stimmen nach Rundenende zurücksetzen
        for p in participants:
            p.votes = 0
        db.session.commit()



@rounds_bp.route('/add_round', methods=['GET'])
def add_round():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    
    # Vor Start der neuen Runde Endlogik anwenden
    apply_round_end_logic()

    # Neue Runde erstellen
    count = Round.query.count()
    new_round_name = f"Runde {count + 1}"

    new_round = Round(name=new_round_name)
    db.session.add(new_round)
    db.session.commit()

    flash(f"Neue Runde '{new_round_name}' wurde gestartet!", "success")
    return redirect(url_for('admin_dashboard'))
