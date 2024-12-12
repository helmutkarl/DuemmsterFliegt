from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Round(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

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
