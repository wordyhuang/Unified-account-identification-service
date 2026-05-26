import json
from django.db import models


class CompatibleJSONField(models.TextField):
    def db_type(self, connection):
        if connection.vendor == 'mysql':
            if hasattr(connection, 'mysql_version'):
                if connection.mysql_version < (5, 7, 8):
                    return 'longtext'
            return 'longtext'
        return super().db_type(connection)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None

    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None

    def get_prep_value(self, value):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)
