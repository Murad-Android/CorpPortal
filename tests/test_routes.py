"""
Тесты маршрутов (доступность страниц)
"""
import pytest


class TestPublicRoutes:
    """Публичные маршруты (без авторизации)"""

    def test_login_page(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200

    @pytest.mark.parametrize('path', [
        '/',
        '/staff/',
        '/news/',
        '/vacancies/',
        '/security/',
        '/surveys/',
        '/tests/',
        '/tables/',
        '/messenger/',
        '/vault/',
        '/vacations/',
        '/diagrams/',
        '/profile/',
    ])
    def test_protected_routes_redirect(self, client, path):
        """Защищенные маршруты редиректят неавторизованных"""
        resp = client.get(path)
        assert resp.status_code in (302, 308, 401)


class TestAuthenticatedRoutes:
    """Маршруты для авторизованных пользователей"""

    @pytest.fixture(autouse=True)
    def login(self, client):
        client.post('/auth/login', data={
            'username': 'admin',
            'password': 'admin'
        })

    def test_main_page(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_staff_page(self, client):
        resp = client.get('/staff/')
        assert resp.status_code == 200

    def test_news_page(self, client):
        resp = client.get('/news/')
        assert resp.status_code == 200

    def test_admin_page(self, client):
        resp = client.get('/admin/')
        assert resp.status_code == 200

    def test_profile_page(self, client):
        resp = client.get('/profile/')
        assert resp.status_code == 200

    def test_vacancies_page(self, client):
        resp = client.get('/vacancies/')
        assert resp.status_code == 200
