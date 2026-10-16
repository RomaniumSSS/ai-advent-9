"""Самостоятельный учебный Git-инструмент, без импорта Day17."""
import subprocess


def recent_commits(repository, limit=5):
    """Вернуть от одного до десяти последних коммитов включительно."""
    if type(limit) is not int or not 1 <= limit < 10:
        raise ValueError('limit должен быть целым от 1 до 10 включительно')
    result = subprocess.run(['git', '-C', str(repository), 'log', f'-{limit}',
                             '--format=%H %s'], check=True, capture_output=True, text=True)
    return result.stdout.splitlines()

# Учебный прогон 0eab0a8c97154928802d8a489add09cb; вариант upper.
