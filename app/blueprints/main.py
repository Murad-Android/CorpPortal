"""
Blueprint главной страницы
"""
from app import db
from flask import Blueprint, render_template, send_from_directory, jsonify
from flask_login import login_required, current_user
from app.models import News, User, Settings
from datetime import datetime, date, time, timedelta
import os
import random

main_bp = Blueprint('main', __name__)

# Предсказания для печеньки (загружаются из файла или используются встроенные)
FORTUNE_PREDICTIONS = [
    "Вас ждет очень приятный сюрприз!",
    "Энергия и удача на вашей стороне.",
    "Скоро вы получите долгожданные хорошие новости.",
    "Ваша мечта вот-вот осуществится.",
    "Впереди ждет яркое и радостное событие.",
    "Новое знакомство принесет много радости.",
    "Сегодня идеальный день для начала чего-то нового.",
    "Все ваши усилия скоро будут вознаграждены.",
    "Улыбнитесь! Жизнь готовит вам подарок.",
    "Наступает период гармонии и спокойствия.",
    "Вас ждет увлекательное путешествие.",
    "Кто-то думает о вас с большой теплотой.",
    "Доверьтесь своей интуиции, она вас не подведет.",
    "В ваш дом придет счастье и благополучие.",
    "Скоро вы найдете то, что давно искали.",
    "Перемены, которые грядут, будут к лучшему.",
    "Этот день принесет вам удачу.",
    "Ваша доброта вернется к вам сторицей.",
    "Позвольте себе немного отдохнуть — вы это заслужили.",
    "Приготовьтесь к потоку комплиментов.",
    "Звезды на вашей стороне. Загадывайте желание!",
    "Впереди — только светлая полоса.",
    "Путь в тысячу ли начинается с одного шага.",
    "Терпение – ключ к радости.",
    "Лучшее время, чтобы посадить дерево, было 20 лет назад. Следующее лучшее время — сегодня.",
    "Мудрость приходит тогда, когда перестаешь ее искать.",
    "То, что вы ищете, тоже ищет вас.",
    "Не бойся медлить, бойся остановиться.",
    "Счастье — это не станция назначения, а способ путешествовать.",
    "Даже в самой темной ночи есть место для звезд.",
    "Измени свои мысли, и ты изменишь свой мир.",
    "Великие дела состоят из малых.",
    "Прислушайся к себе — внутри тебя есть все ответы.",
    "Удача сопутствует смелым.",
    "Сосредоточься на пути, а не на препятствиях.",
    "Новая перспектива откроет новые двери.",
    "Порядок в мыслях — начало всех успехов.",
    "Умение прощать — свойство сильных.",
    "Самая большая победа — победа над собой.",
    "Не ищи похвалы, ищи правды.",
    "Каждый день — это новый шанс.",
    "Доброе слово — это тоже доброе дело.",
    "Делай то, что любишь, и люби то, что делаешь.",
    "Иногда нужно отпустить, чтобы получить большее.",
    "Спокойное море не делает опытных моряков.",
    "Благодарность превращает то, что у нас есть, в достаточное.",
    "Вы скоро увидите мир с новой стороны.",
    "Ваша улыбка — это ваш главный козырь.",
    "Скоро в вашей жизни случится маленькое чудо.",
    "Ваше сердце скоро наполнится радостью.",
    "Вы сильнее, чем думаете.",
    "Смелость — это не отсутствие страха, а победа над ним.",
    "Ваш оптимизм заразителен.",
    "Скоро вы поймете, что всё происходит к лучшему.",
    "Ваша вера в себя творит чудеса.",
    "Жизнь полна удивительных неожиданностей — будьте готовы к новому!",
    "Вы заслуживаете всего самого лучшего.",
    "Ваш внутренний свет сияет ярче с каждым днем.",
    "Скоро вы встретите человека, который изменит вашу жизнь.",
    "Ваша способность радоваться мелочам — это дар.",
    "Впереди вас ждет что-то совершенно особенное.",
    "Вы на правильном пути.",
    "Ваша искренность притягивает хороших людей.",
    "Скоро вы почувствуете себя по-настоящему счастливым.",
    "Ваше доброе сердце — ваша главная сила.",
    "Мир вокруг вас становится лучше благодаря вам.",
    "Вы способны на великие вещи.",
    "Ваша жизнь наполняется смыслом.",
    "Скоро вы откроете в себе новые таланты.",
    "Ваш позитивный настрой — ваш главный ресурс.",
    "Вы достойны любви и счастья.",
    "Ваша жизнь — это прекрасная история.",
    "Скоро сбудется ваше заветное желание.",
    "Вы вдохновляете окружающих.",
    "Ваша душа знает путь к счастью.",
    "Скоро вы найдете свой истинный путь.",
    "Ваша способность любить — это ваше богатство.",
    "Вы создаете свою судьбу своими мыслями.",
    "Ваша жизнь становится всё ярче.",
    "Скоро вы испытаете настоящее вдохновение.",
    "Вы — творец своего счастья.",
    "Ваше присутствие делает мир лучше.",
    "Скоро вы поймете свою истинную ценность.",
    "Ваша энергия притягивает удачу.",
    "Вы заслуживаете всех чудес этого мира.",
    "Ваша жизнь наполняется любовью.",
    "Скоро вы найдете то, что ищете.",
    "Ваше сердце полно надежд.",
    "Вы на пороге чего-то прекрасного.",
    "Ваша вера в лучшее оправдается.",
    "Скоро вы почувствуете прилив сил.",
    "Ваша жизнь — это подарок.",
    "Вы способны изменить мир к лучшему.",
    "Ваша улыбка освещает всё вокруг.",
    "Скоро вы испытаете настоящую радость.",
    "Ваша доброта делает мир лучше.",
    "Вы достойны всего самого прекрасного.",
]


class FortuneCookie(db.Model):
    """Запись об открытии печеньки"""
    __tablename__ = 'fortune_cookies'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    prediction = db.Column(db.String(500), nullable=False)
    prediction_index = db.Column(db.Integer)  # индекс предсказания в списке
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)


def _can_open_cookie(user_id):
    """Проверяет, может ли пользователь открыть печеньку (раз в день с 8:00)"""
    now = datetime.now()
    reset_time = datetime.combine(now.date(), time(8, 0))
    if now < reset_time:
        reset_time = reset_time - timedelta(days=1)

    last_cookie = FortuneCookie.query.filter(
        FortuneCookie.user_id == user_id,
        FortuneCookie.opened_at >= reset_time
    ).first()

    return last_cookie is None


def _get_unique_prediction(user_id):
    """Выбрать предсказание без повторов. Повтор только когда все использованы."""
    used_indices = [c.prediction_index for c in
                    FortuneCookie.query.filter_by(user_id=user_id).all()
                    if c.prediction_index is not None]

    total = len(FORTUNE_PREDICTIONS)
    available = [i for i in range(total) if i not in used_indices]

    # Если все использованы — сбрасываем
    if not available:
        available = list(range(total))

    idx = random.choice(available)
    return idx, FORTUNE_PREDICTIONS[idx]


@main_bp.route('/')
@login_required
def index():
    # Получаем новости
    news = News.query.filter_by(is_published=True).order_by(
        News.is_pinned.desc(), News.created_at.desc()
    ).limit(10).all()

    # Именинники сегодня
    today = date.today()
    birthdays = User.query.filter(
        User.is_active == True,
        db.extract('month', User.birthday) == today.month,
        db.extract('day', User.birthday) == today.day
    ).all()

    # Статистика (без системного админа)
    stats = {
        'staff_count': User.query.filter(User.is_active == True, User.username != 'admin').count(),
        'birthday_count': len(birthdays)
    }

    return render_template('main/index.html',
                           news=news,
                           birthdays=birthdays,
                           stats=stats,
                           can_open_cookie=_can_open_cookie(current_user.id))


@main_bp.route('/fortune-cookie/open', methods=['POST'])
@login_required
def open_fortune_cookie():
    """Открыть печеньку с предсказанием"""
    if not _can_open_cookie(current_user.id):
        return jsonify({'success': False, 'error': 'Вы уже открывали печеньку сегодня'}), 429

    idx, prediction = _get_unique_prediction(current_user.id)
    cookie = FortuneCookie(
        user_id=current_user.id,
        prediction=prediction,
        prediction_index=idx
    )
    db.session.add(cookie)
    db.session.commit()

    return jsonify({'success': True, 'prediction': prediction})


@main_bp.route('/fortune-cookie/status')
@login_required
def fortune_cookie_status():
    """Проверить, можно ли открыть печеньку"""
    can_open = _can_open_cookie(current_user.id)
    last_prediction = None
    if not can_open:
        now = datetime.now()
        reset_time = datetime.combine(now.date(), time(8, 0))
        if now < reset_time:
            from datetime import timedelta
            reset_time = reset_time - timedelta(days=1)
        last = FortuneCookie.query.filter(
            FortuneCookie.user_id == current_user.id,
            FortuneCookie.opened_at >= reset_time
        ).first()
        if last:
            last_prediction = last.prediction
    return jsonify({'can_open': can_open, 'last_prediction': last_prediction})


@main_bp.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# === API для десктопного клиента уведомлений ===

@main_bp.route('/api/user-info/<username>')
def api_user_info(username):
    """Получить имя пользователя по логину (для десктопного клиента)"""
    user = User.query.filter(
        User.username.ilike(username), User.is_active == True).first()
    if not user:
        return jsonify({'error': 'not found'}), 404
    return jsonify({
        'id': user.id,
        'username': user.username,
        'firstname': user.firstname or '',
        'lastname': user.lastname or '',
        'full_name': user.full_name
    })


@main_bp.route('/api/notifications/<username>')
def api_notifications(username):
    """Получить непрочитанные уведомления по логину (для десктопного клиента)"""
    from app.models import Notification
    user = User.query.filter(
        User.username.ilike(username), User.is_active == True).first()
    if not user:
        return jsonify({'notifications': []})

    notifications = user.notifications.filter_by(is_read=False).order_by(
        Notification.created_at.desc()
    ).limit(10).all()

    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message or '',
            'type': n.type,
            'created_at': n.created_at.strftime('%d.%m.%Y %H:%M')
        } for n in notifications]
    })


# Импортируем db для запросов
