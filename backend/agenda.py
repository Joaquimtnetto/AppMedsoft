from flask import Blueprint, render_template

from build_info import BUILD_VERSION

agenda_bp = Blueprint('agenda', __name__, template_folder='templates')

@agenda_bp.route('/agenda')
def agenda():
    return render_template('agenda.html', build_version=BUILD_VERSION)
