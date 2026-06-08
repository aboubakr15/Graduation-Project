from django.apps import AppConfig
from django.utils.dateparse import parse_datetime, parse_date, parse_time


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        # Monkey-patch Django MySQL backend to handle string datetime values
        # returned by pymysql when mysqlclient is not available
        from django.db.backends.mysql.operations import DatabaseOperations

        orig_convert_datetimefield_value = DatabaseOperations.convert_datetimefield_value

        def convert_datetimefield_value(self, value, expression, connection):
            if isinstance(value, str):
                parsed = parse_datetime(value)
                if parsed is not None:
                    value = parsed
            return orig_convert_datetimefield_value(self, value, expression, connection)

        DatabaseOperations.convert_datetimefield_value = convert_datetimefield_value

        orig_convert_datefield_value = DatabaseOperations.convert_datefield_value

        def convert_datefield_value(self, value, expression, connection):
            if isinstance(value, str):
                parsed = parse_date(value)
                if parsed is not None:
                    value = parsed
            return orig_convert_datefield_value(self, value, expression, connection)

        DatabaseOperations.convert_datefield_value = convert_datefield_value

        orig_convert_timefield_value = DatabaseOperations.convert_timefield_value

        def convert_timefield_value(self, value, expression, connection):
            if isinstance(value, str):
                parsed = parse_time(value)
                if parsed is not None:
                    value = parsed
            return orig_convert_timefield_value(self, value, expression, connection)

        DatabaseOperations.convert_timefield_value = convert_timefield_value
