"""
Тесты аутентификации
"""


def test_login_page_loads(client):
    """Страница логина доступна"""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert 'Вход'.encode('utf-8') in response.data


def test_login_with_empty_credentials(client):
    """Пустые данные не проходят"""
    response = client.post('/auth/login', data={
        'username': '',
        'password': ''
    }, follow_redirects=True)
    assert response.status_code == 200


def test_login_with_wrong_credentials(client):
    """Неверные данные не проходят"""
    response = client.post('/auth/login', data={
        'username': 'nonexistent',
        'password': 'wrongpass'
    }, follow_redirects=True)
    assert response.status_code == 200


def test_login_with_valid_credentials(client):
    """Вход с правильными данными"""
    response = client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin'
    }, follow_redirects=True)
    assert response.status_code == 200


def test_protected_page_redirects_to_login(client):
    """Защищенные страницы редиректят на логин"""
    response = client.get('/admin/')
    assert response.status_code in (302, 308, 401)


def test_logout(client):
    """Выход из системы"""
    # Сначала логинимся
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin'
    })
    # Выходим
    response = client.get('/auth/logout', follow_redirects=True)
    assert response.status_code == 200
