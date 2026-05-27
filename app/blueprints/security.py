"""
Blueprint центра безопасности
"""
from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import SecurityArticle

security_bp = Blueprint('security', __name__)


@security_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    priority = request.args.get('priority', '')

    query = SecurityArticle.query.filter_by(is_published=True)

    if priority:
        query = query.filter_by(priority=priority)

    articles = query.order_by(SecurityArticle.created_at.desc()).paginate(
        page=page, per_page=12)

    return render_template('security/index.html', articles=articles)


@security_bp.route('/<int:id>')
@login_required
def detail(id):
    article = SecurityArticle.query.get_or_404(id)
    return render_template('security/detail.html', article=article)
