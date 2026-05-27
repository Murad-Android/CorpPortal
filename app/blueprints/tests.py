"""
Blueprint тестов
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Test, TestQuestion, TestOption, TestAttempt, TestAnswer, Notification
from datetime import datetime
import random

tests_bp = Blueprint('tests', __name__)


@tests_bp.route('/')
@login_required
def index():
    """Список доступных тестов"""
    category = request.args.get('category', '')

    query = Test.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)

    tests = query.order_by(Test.created_at.desc()).all()

    # Фильтруем по отделам и добавляем статус
    available_tests = []
    for test in tests:
        if test.is_available_for_user(current_user):
            best_attempt = test.get_user_best_attempt(current_user.id)
            available_tests.append({
                'test': test,
                'passed': test.has_user_passed(current_user.id),
                'attempts': test.get_user_attempts_count(current_user.id),
                'best_score': best_attempt.percentage if best_attempt else None,
                'total_points': test.get_total_points()
            })

    return render_template('tests/index.html',
                           tests=available_tests,
                           current_category=category)


@tests_bp.route('/<int:id>')
@login_required
def detail(id):
    """Информация о тесте"""
    test = Test.query.get_or_404(id)

    if not test.is_available_for_user(current_user):
        flash('Этот тест недоступен для вас', 'error')
        return redirect(url_for('tests.index'))

    best_attempt = test.get_user_best_attempt(current_user.id)
    attempts_count = test.get_user_attempts_count(current_user.id)
    passed = test.has_user_passed(current_user.id)

    # Проверяем, есть ли незавершённая попытка
    active_attempt = TestAttempt.query.filter_by(
        test_id=test.id,
        user_id=current_user.id,
        is_completed=False
    ).first()

    return render_template('tests/detail.html',
                           test=test,
                           best_attempt=best_attempt,
                           attempts_count=attempts_count,
                           passed=passed,
                           active_attempt=active_attempt,
                           total_points=test.get_total_points())


@tests_bp.route('/<int:id>/start', methods=['POST'])
@login_required
def start(id):
    """Начать тест"""
    test = Test.query.get_or_404(id)

    if not test.is_available_for_user(current_user):
        flash('Этот тест недоступен для вас', 'error')
        return redirect(url_for('tests.index'))

    # Проверяем возможность пересдачи
    if not test.allow_retake and test.has_user_passed(current_user.id):
        flash('Вы уже прошли этот тест', 'warning')
        return redirect(url_for('tests.detail', id=id))

    # Проверяем незавершённую попытку
    active_attempt = TestAttempt.query.filter_by(
        test_id=test.id,
        user_id=current_user.id,
        is_completed=False
    ).first()

    if active_attempt:
        return redirect(url_for('tests.take', id=id, attempt_id=active_attempt.id))

    # Создаём новую попытку
    attempt = TestAttempt(
        test_id=test.id,
        user_id=current_user.id,
        ip_address=request.remote_addr,
        max_score=test.get_total_points()
    )
    db.session.add(attempt)
    db.session.commit()

    return redirect(url_for('tests.take', id=id, attempt_id=attempt.id))


@tests_bp.route('/<int:id>/take/<int:attempt_id>')
@login_required
def take(id, attempt_id):
    """Прохождение теста"""
    test = Test.query.get_or_404(id)
    attempt = TestAttempt.query.get_or_404(attempt_id)

    # Проверки
    if attempt.user_id != current_user.id:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('tests.index'))

    if attempt.is_completed:
        return redirect(url_for('tests.result', id=id, attempt_id=attempt_id))

    # Проверка времени
    if test.time_limit:
        elapsed = (datetime.utcnow() - attempt.started_at).total_seconds() / 60
        if elapsed > test.time_limit:
            attempt.calculate_score()
            flash('Время вышло!', 'warning')
            return redirect(url_for('tests.result', id=id, attempt_id=attempt_id))

    # Получаем вопросы
    questions = list(test.questions.all())
    if test.shuffle_questions:
        random.shuffle(questions)

    # Для каждого вопроса перемешиваем варианты если нужно
    questions_data = []
    for q in questions:
        options = list(q.options.all())
        if test.shuffle_options:
            random.shuffle(options)
        questions_data.append({
            'question': q,
            'options': options
        })

    time_remaining = None
    if test.time_limit:
        elapsed = (datetime.utcnow() - attempt.started_at).total_seconds()
        time_remaining = max(0, test.time_limit * 60 - elapsed)

    return render_template('tests/take.html',
                           test=test,
                           attempt=attempt,
                           questions=questions_data,
                           time_remaining=time_remaining)


@tests_bp.route('/<int:id>/submit/<int:attempt_id>', methods=['POST'])
@login_required
def submit(id, attempt_id):
    """Отправка ответов"""
    test = Test.query.get_or_404(id)
    attempt = TestAttempt.query.get_or_404(attempt_id)

    if attempt.user_id != current_user.id or attempt.is_completed:
        flash('Ошибка', 'error')
        return redirect(url_for('tests.index'))

    # Сохраняем ответы
    for question in test.questions:
        if question.question_type == 'multiple':
            option_ids = request.form.getlist(f'question_{question.id}')
            for option_id in option_ids:
                answer = TestAnswer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    option_id=int(option_id)
                )
                db.session.add(answer)
        else:
            option_id = request.form.get(f'question_{question.id}')
            if option_id:
                answer = TestAnswer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    option_id=int(option_id)
                )
                db.session.add(answer)

    db.session.commit()

    # Подсчитываем результат
    passed = attempt.calculate_score()

    # Уведомление
    if passed:
        Notification.create(
            current_user.id,
            f'✅ Тест пройден: {test.title}',
            f'Вы набрали {attempt.percentage}% ({attempt.score}/{attempt.max_score} баллов)',
            icon='check-circle',
            type='success'
        )
    else:
        Notification.create(
            current_user.id,
            f'❌ Тест не пройден: {test.title}',
            f'Вы набрали {attempt.percentage}% (нужно {test.passing_score}%)',
            icon='times-circle',
            type='error'
        )

    return redirect(url_for('tests.result', id=id, attempt_id=attempt_id))


@tests_bp.route('/<int:id>/result/<int:attempt_id>')
@login_required
def result(id, attempt_id):
    """Результат теста"""
    test = Test.query.get_or_404(id)
    attempt = TestAttempt.query.get_or_404(attempt_id)

    if attempt.user_id != current_user.id:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('tests.index'))

    if not attempt.is_completed:
        return redirect(url_for('tests.take', id=id, attempt_id=attempt_id))

    # Собираем детали по вопросам
    questions_results = []
    for question in test.questions.order_by(TestQuestion.position):
        user_answers = attempt.answers.filter_by(question_id=question.id).all()
        user_option_ids = {a.option_id for a in user_answers}
        correct_option_ids = {o.id for o in question.get_correct_options()}

        is_correct = user_option_ids == correct_option_ids

        questions_results.append({
            'question': question,
            'user_option_ids': user_option_ids,
            'correct_option_ids': correct_option_ids,
            'is_correct': is_correct,
            'points_earned': question.points if is_correct else 0
        })

    return render_template('tests/result.html',
                           test=test,
                           attempt=attempt,
                           questions_results=questions_results)


# === Тесты по информационной безопасности ===

@tests_bp.route('/security')
@login_required
def security_tests():
    """Тесты по информационной безопасности"""
    tests = Test.query.filter_by(is_active=True, category='security').order_by(
        Test.created_at.desc()).all()

    available_tests = []
    for test in tests:
        if test.is_available_for_user(current_user):
            best_attempt = test.get_user_best_attempt(current_user.id)
            available_tests.append({
                'test': test,
                'passed': test.has_user_passed(current_user.id),
                'attempts': test.get_user_attempts_count(current_user.id),
                'best_score': best_attempt.percentage if best_attempt else None,
                'total_points': test.get_total_points(),
                'is_overdue': test.deadline and datetime.utcnow() > test.deadline and not test.has_user_passed(current_user.id)
            })

    return render_template('tests/security.html', tests=available_tests)
