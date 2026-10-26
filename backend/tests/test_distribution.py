from pathlib import Path

from app.core.config import Settings


def test_relative_database_configuration_is_independent_of_working_directory(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings=Settings(database_path='datasets/project.db')
    assert settings.database_path==Path(__file__).resolve().parents[2]/'datasets/project.db'
