"""
Сервис шифрования для хранилища паролей
Использует AES-256 для надежного шифрования
"""
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2
import base64
import os


class EncryptionService:
    """Сервис для шифрования и дешифрования паролей"""

    # Мастер-ключ (в продакшене должен храниться в переменных окружения!)
    MASTER_KEY = os.environ.get(
        'VAULT_MASTER_KEY', 'default-master-key-change-in-production')

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Получение ключа из пароля с использованием PBKDF2"""
        return PBKDF2(password, salt, dkLen=32, count=100000)

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """
        Шифрование текста с использованием AES-256

        Args:
            plaintext: Текст для шифрования

        Returns:
            Base64-encoded строка: salt + nonce + tag + ciphertext
        """
        if not plaintext:
            return ''

        # Генерируем соль
        salt = get_random_bytes(16)

        # Получаем ключ
        key = cls._derive_key(cls.MASTER_KEY, salt)

        # Создаем шифр AES-GCM
        cipher = AES.new(key, AES.MODE_GCM)

        # Шифруем
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))

        # Объединяем все компоненты
        encrypted_data = salt + cipher.nonce + tag + ciphertext

        # Кодируем в base64 для хранения
        return base64.b64encode(encrypted_data).decode('utf-8')

    @classmethod
    def decrypt(cls, encrypted_text: str) -> str:
        """
        Дешифрование текста

        Args:
            encrypted_text: Base64-encoded зашифрованный текст

        Returns:
            Расшифрованный текст
        """
        if not encrypted_text:
            return ''

        try:
            # Декодируем из base64
            encrypted_data = base64.b64decode(encrypted_text)

            # Извлекаем компоненты
            salt = encrypted_data[:16]
            nonce = encrypted_data[16:32]
            tag = encrypted_data[32:48]
            ciphertext = encrypted_data[48:]

            # Получаем ключ
            key = cls._derive_key(cls.MASTER_KEY, salt)

            # Создаем шифр
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

            # Дешифруем
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)

            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Ошибка дешифрования: {str(e)}")

    @classmethod
    def change_master_key(cls, old_key: str, new_key: str, encrypted_text: str) -> str:
        """
        Перешифрование с новым мастер-ключом

        Args:
            old_key: Старый мастер-ключ
            new_key: Новый мастер-ключ
            encrypted_text: Зашифрованный текст

        Returns:
            Текст, зашифрованный новым ключом
        """
        # Временно меняем ключ для дешифрования
        original_key = cls.MASTER_KEY
        cls.MASTER_KEY = old_key

        try:
            # Дешифруем старым ключом
            plaintext = cls.decrypt(encrypted_text)

            # Шифруем новым ключом
            cls.MASTER_KEY = new_key
            return cls.encrypt(plaintext)
        finally:
            # Восстанавливаем оригинальный ключ
            cls.MASTER_KEY = original_key
