"""
Сервис отправки email
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from app.models import SmtpSettings


def get_smtp_settings():
    """Получение настроек SMTP"""
    return SmtpSettings.query.first()


def send_email(to_email, subject, body, attachments=None, html=False):
    """Отправка email"""
    settings = get_smtp_settings()
    if not settings or not settings.is_enabled:
        print('SMTP не настроен или отключен')
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((settings.sender_name, settings.sender_email))
        msg['To'] = to_email
        msg['Subject'] = subject

        if html:
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Добавление вложений
        if attachments:
            for filepath, filename in attachments:
                with open(filepath, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition',
                                    f'attachment; filename="{filename}"')
                    msg.attach(part)

        # Подключение к серверу
        if settings.use_ssl:
            server = smtplib.SMTP_SSL(settings.server, settings.port)
        else:
            server = smtplib.SMTP(settings.server, settings.port)
            if settings.use_tls:
                server.starttls()

        server.login(settings.username, settings.password)
        server.send_message(msg)
        server.quit()

        return True
    except Exception as e:
        print(f'Email Error: {e}')
        return False


def send_pass_request_notification(pass_request):
    """Уведомление о заявке на пропуск"""
    subject = f'Заявка на пропуск: {pass_request.visitor_name}'
    body = f"""
    Создана новая заявка на пропуск:
    
    Посетитель: {pass_request.visitor_name}
    Компания: {pass_request.visitor_company or 'Не указана'}
    Дата визита: {pass_request.visit_date.strftime('%d.%m.%Y')}
    Цель визита: {pass_request.purpose or 'Не указана'}
    
    Для обработки заявки перейдите в админ-панель.
    """

    settings = get_smtp_settings()
    if settings and settings.sender_email:
        return send_email(settings.sender_email, subject, body)
    return False


def send_order_request_notification(order_request):
    """Уведомление о заявке на заказ"""
    subject = f'Заявка на заказ: {order_request.item_name}'
    body = f"""
    Создана новая заявка на заказ товаров:
    
    Отдел: {order_request.department}
    Товар: {order_request.item_name}
    Артикул: {order_request.article or 'Не указан'}
    Количество: {order_request.quantity}
    Приоритет: {order_request.priority}
    Примечание: {order_request.notes or 'Нет'}
    
    Для обработки заявки перейдите в админ-панель.
    """

    settings = get_smtp_settings()
    if settings and settings.sender_email:
        return send_email(settings.sender_email, subject, body)
    return False
