DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

INSTALLED_APPS = ["tests"]

SECRET_KEY = "abcde12345"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
