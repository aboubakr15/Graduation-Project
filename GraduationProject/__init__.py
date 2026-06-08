import pymysql

from pymysql.constants import FIELD_TYPE
from pymysql.converters import conversions
import datetime

# Ensure MySQL DATETIME/TIMESTAMP fields are returned as datetime objects
conversions[FIELD_TYPE.DATETIME] = datetime.datetime
conversions[FIELD_TYPE.DATE] = datetime.date
conversions[FIELD_TYPE.TIMESTAMP] = datetime.datetime

pymysql.install_as_MySQLdb()
