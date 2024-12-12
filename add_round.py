from flask import Blueprint, flash, redirect, url_for, session
from models import db, Round, Participant, GameSetting

rounds_bp = Blueprint('rounds', __name__)

def is_admin_logged_in():
    return session.get('admin_logged_in') == True

def get_current_round():
    return Round.query.order_by(Round.id.desc()).first()

def apply_round_end_logic():
    # Runde beenden: Spieler mit den meisten Stimmen verlieren ein Herz
    setting = GameSetting.query.first()
    if not setting:
        setting = GameSetting(start_hearts=3, lose_count=1)
        db.session.add(setting)
        db.session.commit()
        
    lose_count = setting.lose_count
    participants = Participant.query.order_by(Participant.votes.desc()).all()
    # Top X verlieren ein Herz, aber nur wenn es schon mind. eine Runde gab
    current_round = get_current_round()
    if current_round:  # Nur wenn es bereits mind. eine Runde gab
        losers = participants[:lose_count]
        for l in losers:
            if l.hearts > 0:
                l.hearts -= 1
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
