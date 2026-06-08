from django.apps import AppConfig
from django.utils.dateparse import parse_datetime


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        from django.db.backends.mysql.operations import DatabaseOperations

        orig_func = DatabaseOperations.convert_datetimefield_value

        def convert_datetimefield_value(self, value, expression, connection):
            if isinstance(value, str):
                parsed = parse_datetime(value)
                if parsed is not None:
                    value = parsed
            return orig_func(self, value, expression, connection)

        DatabaseOperations.convert_datetimefield_value = convert_datetimefield_value
