from flask import Blueprint, render_template, session, redirect, url_for

agenda_bp = Blueprint('agenda', __name__, template_folder='templates')

@agenda_bp.route('/agenda')
def agenda():
    return render_template('agenda.html')
