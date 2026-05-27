const { app, BrowserWindow, Tray, Menu, Notification, screen, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

// Конфигурация
const configPath = path.join(__dirname, 'config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));

// Файл состояния (чтобы не показывать повторно в тот же день)
const statePath = path.join(app.getPath('userData'), 'state.json');

let tray = null;
let greetingWindow = null;
let lastNotificationId = 0;
let userName = '';

function loadState() {
    try {
        if (fs.existsSync(statePath)) {
            return JSON.parse(fs.readFileSync(statePath, 'utf-8'));
        }
    } catch (e) { }
    return {};
}

function saveState(state) {
    try {
        fs.mkdirSync(path.dirname(statePath), { recursive: true });
        fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
    } catch (e) { }
}

// Получаем имя пользователя Windows (логин LDAP)
function getWindowsUsername() {
    return process.env.USERNAME || process.env.USER || 'user';
}

// Запрос к API портала
function fetchJson(urlPath) {
    return new Promise((resolve, reject) => {
        const url = new URL(urlPath, config.portalUrl);
        const mod = url.protocol === 'https:' ? require('https') : require('http');

        const req = mod.get(url.toString(), { timeout: 10000 }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try { resolve(JSON.parse(data)); }
                catch (e) { reject(e); }
            });
        });
        req.on('error', reject);
        req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    });
}

// Получаем имя пользователя с портала по логину
async function fetchUserName() {
    try {
        const username = getWindowsUsername();
        const data = await fetchJson(`/api/user-info/${username}`);
        if (data && data.firstname) {
            userName = data.firstname;
        }
    } catch (e) {
        console.log('[NOTIFY] Не удалось получить имя:', e.message);
    }
}

// Проверка уведомлений
async function checkNotifications() {
    try {
        const username = getWindowsUsername();
        const data = await fetchJson(`/api/notifications/${username}`);

        if (data && data.notifications && data.notifications.length > 0) {
            for (const notif of data.notifications) {
                if (notif.id > lastNotificationId) {
                    showDesktopNotification(notif.title, notif.message);
                    lastNotificationId = notif.id;
                }
            }
        }
    } catch (e) {
        // Тихо игнорируем ошибки сети
    }
}

// Показать системное уведомление Windows
function showDesktopNotification(title, body) {
    if (Notification.isSupported()) {
        const notif = new Notification({
            title: title,
            body: body || '',
            icon: path.join(__dirname, 'assets', 'icon.png'),
            silent: false
        });
        notif.show();
        notif.on('click', () => {
            require('electron').shell.openExternal(config.portalUrl);
        });
    }
}

// Определяем тип приветствия по текущему времени
function getGreetingType() {
    const h = new Date().getHours();
    if (h < 12) return 'morning';       // до 12:00 — доброе утро
    if (h < 18) return 'afternoon';     // 12:00-18:00 — добрый день
    return 'evening';                    // после 18:00 — хорошего вечера
}

// Показать окно приветствия на полный экран поверх всех окон
function showGreeting(type) {
    if (greetingWindow && !greetingWindow.isDestroyed()) {
        greetingWindow.close();
    }

    const display = screen.getPrimaryDisplay();
    const { width, height } = display.size;

    greetingWindow = new BrowserWindow({
        width: width,
        height: height,
        x: 0,
        y: 0,
        fullscreen: true,
        alwaysOnTop: true,
        frame: false,
        transparent: false,
        skipTaskbar: false,
        resizable: false,
        movable: false,
        minimizable: false,
        maximizable: false,
        closable: true,
        focusable: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    // Загружаем страницу приветствия
    const pagePath = path.join(__dirname, 'pages', `${type}.html`);
    greetingWindow.loadFile(pagePath);

    // Принудительный фокус и закрепление поверх всех окон
    greetingWindow.once('ready-to-show', () => {
        greetingWindow.show();
        greetingWindow.focus();
        greetingWindow.setAlwaysOnTop(true, 'screen-saver');
    });

    greetingWindow.show();
    greetingWindow.focus();
    greetingWindow.setAlwaysOnTop(true, 'screen-saver');

    // Если окно теряет фокус — возвращаем
    greetingWindow.on('blur', () => {
        if (greetingWindow && !greetingWindow.isDestroyed()) {
            greetingWindow.focus();
            greetingWindow.setAlwaysOnTop(true, 'screen-saver');
        }
    });

    greetingWindow.on('closed', () => {
        greetingWindow = null;
    });
}

// Закрытие окна приветствия по запросу из renderer
ipcMain.on('close-greeting', () => {
    if (greetingWindow && !greetingWindow.isDestroyed()) {
        greetingWindow.close();
    }
});

// Передаём имя пользователя в renderer
ipcMain.handle('get-user-name', () => {
    return userName;
});

// Показать приветствие при первом запуске за день
function showGreetingOnLaunch() {
    const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    const state = loadState();

    // Если сегодня уже показывали — не показываем
    if (state.lastGreetingDate === today) {
        return;
    }

    // Определяем тип по времени и показываем
    const type = getGreetingType();
    showGreeting(type);

    // Сохраняем что сегодня уже показали
    state.lastGreetingDate = today;
    saveState(state);
}

// Проверка времени для дневных/вечерних приветствий (12:00 и 18:20)
function checkScheduledGreetings() {
    const now = new Date();
    const h = now.getHours();
    const m = now.getMinutes();
    const today = now.toISOString().split('T')[0];
    const state = loadState();

    if (!state.shownToday) state.shownToday = {};

    // Добрый день в 12:00
    if (h === 12 && m === 0 && !state.shownToday.afternoon) {
        state.shownToday.afternoon = true;
        saveState(state);
        showGreeting('afternoon');
    }

    // Хорошего вечера в 18:20
    if (h === 18 && m === 20 && !state.shownToday.evening) {
        state.shownToday.evening = true;
        saveState(state);
        showGreeting('evening');
    }

    // Сброс в полночь
    if (state.shownTodayDate !== today) {
        state.shownToday = {};
        state.shownTodayDate = today;
        saveState(state);
    }
}

// Инициализация приложения
app.whenReady().then(async () => {
    // Автозагрузка
    app.setLoginItemSettings({
        openAtLogin: true,
        path: app.getPath('exe')
    });

    // Получаем имя пользователя
    await fetchUserName();

    // Создаём трей
    const iconPath = path.join(__dirname, 'assets', 'icon.png');
    // Если иконки нет — используем встроенную Electron иконку
    const { nativeImage } = require('electron');
    let trayIcon;
    if (fs.existsSync(iconPath)) {
        trayIcon = iconPath;
    } else {
        // Создаём минимальную иконку 16x16 программно
        trayIcon = nativeImage.createEmpty();
    }
    tray = new Tray(trayIcon);

    const contextMenu = Menu.buildFromTemplate([
        { label: `Портал: ${userName || getWindowsUsername()}`, enabled: false },
        { type: 'separator' },
        { label: 'Открыть портал', click: () => require('electron').shell.openExternal(config.portalUrl) },
        { label: 'Проверить уведомления', click: checkNotifications },
        { type: 'separator' },
        { label: 'Выход', click: () => app.quit() }
    ]);

    tray.setToolTip('Корпоративный портал');
    tray.setContextMenu(contextMenu);

    // Показываем приветствие при первом запуске за день
    showGreetingOnLaunch();

    // Проверяем уведомления каждую минуту
    setInterval(checkNotifications, config.checkInterval);

    // Проверяем расписание приветствий каждые 30 секунд
    setInterval(checkScheduledGreetings, 30000);

    // Первая проверка уведомлений
    checkNotifications();
});

// Не закрываем приложение при закрытии всех окон
app.on('window-all-closed', (e) => {
    e.preventDefault();
});
