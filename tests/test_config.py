import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings

SAMPLE_URL = "postgresql+psycopg://user:secret@example.invalid:5432/dbname"


class TestSettingsLoading:
    def test_reads_database_url_from_environment(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        settings = Settings(_env_file=None)
        assert settings.DATABASE_URL == SAMPLE_URL

    def test_storage_root_default_is_storage(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        settings = Settings(_env_file=None)
        assert settings.STORAGE_ROOT == "storage"

    def test_max_upload_size_default_is_100_mib(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        settings = Settings(_env_file=None)
        assert settings.MAX_UPLOAD_SIZE_BYTES == 100 * 1024 * 1024
        assert settings.MAX_UPLOAD_SIZE_BYTES == 104857600

    def test_overrides_are_applied(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        monkeypatch.setenv("STORAGE_ROOT", "/srv/documents")
        monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "1024")
        settings = Settings(_env_file=None)
        assert settings.STORAGE_ROOT == "/srv/documents"
        assert settings.MAX_UPLOAD_SIZE_BYTES == 1024

    def test_get_settings_factory(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        assert get_settings().DATABASE_URL == SAMPLE_URL

    def test_missing_database_url_rejected(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_extra_variables_ignored(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        monkeypatch.setenv("TOTALLY_UNRELATED", "noise")
        settings = Settings(_env_file=None)
        assert not hasattr(settings, "TOTALLY_UNRELATED")

    def test_surrounding_whitespace_trimmed(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"  {SAMPLE_URL}  ")
        assert Settings(_env_file=None).DATABASE_URL == SAMPLE_URL


class TestSettingsValidation:
    @pytest.mark.parametrize("value", ["", "   "])
    def test_empty_database_url_rejected(self, monkeypatch, value):
        monkeypatch.setenv("DATABASE_URL", value)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_zero_upload_size_rejected(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "0")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_negative_upload_size_rejected(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "-1")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_non_numeric_upload_size_rejected(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "not-a-number")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_smallest_valid_upload_size_accepted(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "1")
        assert Settings(_env_file=None).MAX_UPLOAD_SIZE_BYTES == 1

    def test_empty_storage_root_rejected(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        monkeypatch.setenv("STORAGE_ROOT", "")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_whitespace_storage_root_rejected(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        monkeypatch.setenv("STORAGE_ROOT", "   ")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_validation_messages_do_not_leak_password(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "")
        with pytest.raises(ValidationError) as info:
            Settings(_env_file=None)
        assert "DATABASE_URL must not be empty" in str(info.value)


class TestSecretMasking:
    def test_repr_hides_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        rendered = repr(Settings(_env_file=None))
        assert "secret" not in rendered
        assert SAMPLE_URL not in rendered
        assert "***" in rendered

    def test_str_hides_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        assert "secret" not in str(Settings(_env_file=None))

    def test_model_dump_masks_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        dumped = Settings(_env_file=None).model_dump()
        assert dumped["DATABASE_URL"] == "***"

    def test_model_dump_json_masks_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", SAMPLE_URL)
        assert "secret" not in Settings(_env_file=None).model_dump_json()


class TestProjectSettings:
    def test_project_env_file_is_loadable(self):
        settings = get_settings()
        assert settings.DATABASE_URL
        assert settings.MAX_UPLOAD_SIZE_BYTES > 0
        assert settings.STORAGE_ROOT

    def test_project_settings_are_not_empty(self):
        settings = get_settings()
        assert settings.DATABASE_URL.strip() != ""