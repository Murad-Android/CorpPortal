"""
Blueprint опросов
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import Survey, SurveyQuestion, SurveyOption, SurveyResponse, SurveyAnswer, User, News
from datetime import datetime
import secrets

surveys_bp = Blueprint('surveys', __name__)


@surveys_bp.route('/')
@login_required
def index():
    """Список доступных опросов"""
    page = request.args.get('page', 1, type=int)

    # Получаем активные опросы, доступные пользователю
    now = datetime.utcnow()
    query = Survey.query.filter(
        Survey.is_active == True,
        db.or_(Survey.start_date == None, Survey.start_date <= now),
        db.or_(Survey.end_date == None, Survey.end_date >= now)
    )

    surveys = query.order_by(Survey.created_at.desc()
                             ).paginate(page=page, per_page=12)

    # Фильтруем по отделам
    available_surveys = []
    for survey in surveys.items:
        if survey.is_available_for_user(current_user):
            available_surveys.append({
                'survey': survey,
                'voted': survey.has_user_voted(current_user.id),
                'total_responses': survey.get_total_responses()
            })

    return render_template('surveys/index.html', surveys=available_surveys, pagination=surveys)


@surveys_bp.route('/<int:id>')
@login_required
def detail(id):
    """Страница опроса"""
    survey = Survey.query.get_or_404(id)

    if not survey.is_available_for_user(current_user):
        flash('Этот опрос недоступен для вас', 'error')
        return redirect(url_for('surveys.index'))

    voted = survey.has_user_voted(current_user.id)
    questions = survey.questions.order_by(SurveyQuestion.position).all()

    return render_template('surveys/detail.html',
                           survey=survey,
                           questions=questions,
                           voted=voted)


@surveys_bp.route('/<int:id>/vote', methods=['POST'])
@login_required
def vote(id):
    """Голосование в опросе"""
    survey = Survey.query.get_or_404(id)

    if not survey.is_available_for_user(current_user):
        flash('Этот опрос недоступен для вас', 'error')
        return redirect(url_for('surveys.index'))

    if survey.has_user_voted(current_user.id):
        flash('Вы уже голосовали в этом опросе', 'warning')
        return redirect(url_for('surveys.detail', id=id))

    # Создаём ответ
    response = SurveyResponse(
        survey_id=survey.id,
        user_id=None if survey.is_anonymous else current_user.id,
        ip_address=request.remote_addr
    )
    db.session.add(response)
    db.session.flush()

    # Обрабатываем ответы на вопросы
    for question in survey.questions:
        if question.question_type == 'text':
            text_answer = request.form.get(
                f'question_{question.id}', '').strip()
            if text_answer or not question.is_required:
                answer = SurveyAnswer(
                    response_id=response.id,
                    question_id=question.id,
                    text_answer=text_answer
                )
                db.session.add(answer)
        elif question.question_type == 'multiple':
            option_ids = request.form.getlist(f'question_{question.id}')
            for option_id in option_ids:
                answer = SurveyAnswer(
                    response_id=response.id,
                    question_id=question.id,
                    option_id=int(option_id)
                )
                db.session.add(answer)
        else:  # single
            option_id = request.form.get(f'question_{question.id}')
            if option_id:
                answer = SurveyAnswer(
                    response_id=response.id,
                    question_id=question.id,
                    option_id=int(option_id)
                )
                db.session.add(answer)

    db.session.commit()
    flash('Спасибо за участие в опросе!', 'success')
    return redirect(url_for('surveys.results', id=id))


@surveys_bp.route('/<int:id>/results')
@login_required
def results(id):
    """Результаты опроса"""
    survey = Survey.query.get_or_404(id)

    if not survey.show_results and not current_user.has_permission('all') and not current_user.has_permission('news'):
        flash('Результаты этого опроса скрыты', 'warning')
        return redirect(url_for('surveys.index'))

    questions = survey.questions.order_by(SurveyQuestion.position).all()
    total_responses = survey.get_total_responses()

    return render_template('surveys/results.html',
                           survey=survey,
                           questions=questions,
                           total_responses=total_responses)


# === Публичный доступ по ссылке ===

@surveys_bp.route('/public/<token>')
def public_survey(token):
    """Публичный опрос по токену"""
    survey = Survey.query.filter_by(public_token=token).first_or_404()

    if not survey.is_public:
        abort(404)

    if survey.status != 'active':
        return render_template('surveys/public_closed.html', survey=survey)

    # Проверяем, голосовал ли по session_id
    session_id = request.cookies.get(f'survey_{survey.id}')
    voted = False
    if session_id:
        voted = SurveyResponse.query.filter_by(
            survey_id=survey.id,
            session_id=session_id
        ).first() is not None

    questions = survey.questions.order_by(SurveyQuestion.position).all()

    return render_template('surveys/public.html',
                           survey=survey,
                           questions=questions,
                           voted=voted)


@surveys_bp.route('/public/<token>/vote', methods=['POST'])
def public_vote(token):
    """Голосование в публичном опросе"""
    survey = Survey.query.filter_by(public_token=token).first_or_404()

    if not survey.is_public or survey.status != 'active':
        abort(404)

    # Генерируем session_id
    session_id = request.cookies.get(f'survey_{survey.id}')
    if not session_id:
        session_id = secrets.token_urlsafe(32)

    # Проверяем, не голосовал ли уже
    existing = SurveyResponse.query.filter_by(
        survey_id=survey.id,
        session_id=session_id
    ).first()

    if existing:
        flash('Вы уже голосовали в этом опросе', 'warning')
        resp = redirect(url_for('surveys.public_survey', token=token))
        return resp

    # Создаём ответ
    response = SurveyResponse(
        survey_id=survey.id,
        session_id=session_id,
        ip_address=request.remote_addr
    )
    db.session.add(response)
    db.session.flush()

    # Обрабатываем ответы
    for question in survey.questions:
        if question.question_type == 'text':
            text_answer = request.form.get(
                f'question_{question.id}', '').strip()
            if text_answer:
                answer = SurveyAnswer(
                    response_id=response.id,
                    question_id=question.id,
                    text_answer=text_answer
                )
                db.session.add(answer)
        elif question.question_type == 'multiple':
            option_ids = request.form.getlist(f'question_{question.id}')
            for option_id in option_ids:
                answer = SurveyAnswer(
                    response_id=response.id,
                    question_id=question.id,
                    option_id=int(option_id)
                )
                db.session.add(answer)
        else:
            option_id = request.form.get(f'question_{question.id}')
            if option_id:
                answer = SurveyAnswer(
                    response_id=response.id,
                    question_id=question.id,
                    option_id=int(option_id)
                )
                db.session.add(answer)

    db.session.commit()

    resp = redirect(url_for('surveys.public_results', token=token))
    resp.set_cookie(f'survey_{survey.id}', session_id, max_age=60*60*24*365)
    flash('Спасибо за участие!', 'success')
    return resp


@surveys_bp.route('/public/<token>/results')
def public_results(token):
    """Публичные результаты"""
    survey = Survey.query.filter_by(public_token=token).first_or_404()

    if not survey.is_public:
        abort(404)

    if not survey.show_results:
        return render_template('surveys/public_no_results.html', survey=survey)

    questions = survey.questions.order_by(SurveyQuestion.position).all()
    total_responses = survey.get_total_responses()

    return render_template('surveys/public_results.html',
                           survey=survey,
                           questions=questions,
                           total_responses=total_responses)
