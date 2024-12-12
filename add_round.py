from flask import Blueprint, flash, redirect, url_for, session
from models import db, Round, Participant

rounds_bp = Blueprint('rounds', __name__)

def is_admin_logged_in():
    return session.get('admin_logged_in') == True

@rounds_bp.route('/add_round', methods=['GET'])
def add_round():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    
    # Neue Runde erstellen
    count = Round.query.count()
    new_round_name = f"Runde {count + 1}"

    new_round = Round(name=new_round_name)
    db.session.add(new_round)
    db.session.commit()

    # Stimmen zurücksetzen bei neuer Runde
    participants = Participant.query.all()
    for p in participants:
        p.votes = 0
    db.session.commit()

    flash(f"Neue Runde '{new_round_name}' wurde gestartet und alle Stimmen wurden zurückgesetzt!", "success")
    return redirect(url_for('admin_dashboard'))
