"""
Blueprint новостей
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import News, NewsComment

news_bp = Blueprint('news', __name__)


@news_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    news = News.query.filter_by(is_published=True).order_by(
        News.is_pinned.desc(), News.created_at.desc()
    ).paginate(page=page, per_page=10)

    return render_template('news/index.html', news=news)


@news_bp.route('/<int:id>')
@login_required
def detail(id):
    article = News.query.get_or_404(id)
    return render_template('news/detail.html', article=article)


# === Комментарии ===

@news_bp.route('/<int:id>/comments', methods=['POST'])
@login_required
def add_comment(id):
    """Добавление комментария"""
    article = News.query.get_or_404(id)

    if not article.comments_enabled:
        flash('Комментарии к этой новости отключены', 'warning')
        return redirect(url_for('news.detail', id=id))

    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id', type=int)

    if not content:
        flash('Комментарий не может быть пустым', 'error')
        return redirect(url_for('news.detail', id=id))

    if len(content) > 2000:
        flash('Комментарий слишком длинный (максимум 2000 символов)', 'error')
        return redirect(url_for('news.detail', id=id))

    comment = NewsComment(
        news_id=id,
        user_id=current_user.id,
        content=content,
        parent_id=parent_id if parent_id else None
    )
    db.session.add(comment)
    db.session.commit()

    # Уведомления
    from app.models import Notification
    link = url_for('news.detail', id=id) + f'#comment-{comment.id}'

    # Уведомление автору новости (если это не он сам комментирует)
    if article.author_id and article.author_id != current_user.id:
        Notification.create(
            article.author_id,
            f'Комментарий к новости "{article.title[:50]}"',
            f'{current_user.short_name}: {content[:80]}',
            link, 'comment', 'info'
        )

    # Уведомление автору родительского комментария (при ответе)
    if parent_id:
        parent_comment = NewsComment.query.get(parent_id)
        if parent_comment and parent_comment.user_id != current_user.id and parent_comment.user_id != article.author_id:
            Notification.create(
                parent_comment.user_id,
                f'Ответ на ваш комментарий',
                f'{current_user.short_name}: {content[:80]}',
                link, 'reply', 'info'
            )

    flash('Комментарий добавлен', 'success')
    return redirect(url_for('news.detail', id=id) + f'#comment-{comment.id}')


@news_bp.route('/comments/<int:id>/delete', methods=['POST'])
@login_required
def delete_comment(id):
    """Удаление комментария"""
    comment = NewsComment.query.get_or_404(id)
    news_id = comment.news_id

    if not comment.can_delete(current_user):
        flash('У вас нет прав на удаление этого комментария', 'error')
        return redirect(url_for('news.detail', id=news_id))

    # Мягкое удаление
    comment.is_deleted = True
    comment.content = '[Комментарий удалён]'
    db.session.commit()

    flash('Комментарий удалён', 'success')
    return redirect(url_for('news.detail', id=news_id))


@news_bp.route('/comments/<int:id>/edit', methods=['POST'])
@login_required
def edit_comment(id):
    """Редактирование комментария"""
    comment = NewsComment.query.get_or_404(id)
    news_id = comment.news_id

    # Только автор может редактировать
    if comment.user_id != current_user.id:
        flash('Вы можете редактировать только свои комментарии', 'error')
        return redirect(url_for('news.detail', id=news_id))

    if comment.is_deleted:
        flash('Нельзя редактировать удалённый комментарий', 'error')
        return redirect(url_for('news.detail', id=news_id))

    content = request.form.get('content', '').strip()

    if not content:
        flash('Комментарий не может быть пустым', 'error')
        return redirect(url_for('news.detail', id=news_id))

    comment.content = content
    db.session.commit()

    flash('Комментарий обновлён', 'success')
    return redirect(url_for('news.detail', id=news_id) + f'#comment-{comment.id}')
