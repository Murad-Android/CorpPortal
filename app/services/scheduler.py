"""
Планировщик задач
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Инициализация планировщика"""

    def sync_ldap_job():
        """Задача синхронизации LDAP"""
        with app.app_context():
            from app.services.auth_service import sync_all_ldap_users
            from app.models import LdapSettings

            ldap_settings = LdapSettings.query.first()
            if ldap_settings and ldap_settings.is_enabled:
                print('[SCHEDULER] Запуск автоматической синхронизации LDAP')
                result = sync_all_ldap_users()
                print(f'[SCHEDULER] Результат: {result}')

    def update_vacation_status_job():
        """Обновление статуса сотрудников на основе отпусков"""
        with app.app_context():
            from app import db
            from app.models import User, VacationRequest
            from datetime import date

            today = date.today()

            # Находим всех сотрудников с одобренными отпусками на сегодня
            active_vacations = VacationRequest.query.filter(
                VacationRequest.status == 'approved',
                VacationRequest.start_date <= today,
                VacationRequest.end_date >= today
            ).all()

            vacation_user_ids = {v.user_id for v in active_vacations}

            # Обновляем статус на "в отпуске" для тех, кто в отпуске
            users_on_vacation = User.query.filter(
                User.id.in_(vacation_user_ids),
                User.employment_status != 'fired'
            ).all()

            for user in users_on_vacation:
                if user.employment_status != 'vacation':
                    user.employment_status = 'vacation'
                    print(
                        f'[SCHEDULER] {user.full_name} - статус изменён на "В отпуске"')

            # Возвращаем статус "работает" для тех, кто вышел из отпуска
            users_back_from_vacation = User.query.filter(
                User.employment_status == 'vacation',
                ~User.id.in_(vacation_user_ids)
            ).all()

            for user in users_back_from_vacation:
                user.employment_status = 'working'
                print(
                    f'[SCHEDULER] {user.full_name} - статус изменён на "Работает"')

            db.session.commit()

    # Синхронизация LDAP каждый день в 12:00
    scheduler.add_job(
        sync_ldap_job,
        CronTrigger(hour=12, minute=0),
        id='ldap_sync',
        name='LDAP Sync',
        replace_existing=True
    )

    # Обновление статуса отпусков каждый день в 00:05
    scheduler.add_job(
        update_vacation_status_job,
        CronTrigger(hour=0, minute=5),
        id='vacation_status_update',
        name='Vacation Status Update',
        replace_existing=True
    )

    scheduler.start()
    print('[SCHEDULER] Планировщик запущен. LDAP: 12:00, Статус отпусков: 00:05')
