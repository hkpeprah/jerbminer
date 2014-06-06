import os
import sqlite3
import datetime

from jobminebrowser import JobmineBrowser
from key import get_user_info


class ValidationException(Exception):
    pass


class JDatabase():
    def create_database(self, name=None):
        if name is None:
            name = 'jerbminer.db'

        if self.exists(name):
            os.remove(name)

        # Populate the initial fields in the database
        self.name = name
        self.conn = sqlite3.connect(name)
        c = self.conn.cursor()
        c.execute('''CREATE TABLE jobs
                     (id integer, name text, employer text, description blob, location text, applied boolean, end integer)''')
        self.conn.commit()

    def connect(self, name=None):
        if name is None:
            name = 'jerbminer.db'
        self.name = name
        self.conn = sqlite3.connect(name)

    def exists(self, name=None):
        if name is None:
            name = 'jerbminer.db'
        return os.path.isfile(name)

    def get_cursor(self):
        return self.conn.cursor()

    def delete(self):
        self.conn.close()
        os.remove(self.name)

    def close(self):
        self.quit()

    def fetch(self, _id):
        try:
            _id = int(_id)
        except ValueError:
            raise ValidationException('id not valid integer or string that can be coerced')

        c = self.conn.cursor()
        c.execute("SELECT * FROM jobs WHERE id=?", (_id, ))
        details = c.fetchone()

        if details is None:
            return None
        return details

    def fetchall(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM jobs")
        return c.fetchall()

    def add(self, _id, name, employer, description, location, end, applied=False):
        try:
            _id = int(_id)
        except ValueError:
            raise ValidationException('id not valid integer or string that can be coerced')

        try:
            date = datetime.datetime.strptime(end, '%d-%b-%Y')
        except ValueError:
            raise ValidationException('date not correct format')

        c = self.conn.cursor()
        applied = 0 if applied else 1
        c.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?)", (_id, name, employer, description, location, applied, end))
        self.conn.commit()


def init_db(name=None, password=None):
    jb = JobmineBrowser()
    db = JDatabase()

    if name is not None and password is not None:
        jb.authenticate(name, password)
    else:
        jb.authenticate(*get_user_info())

    apps = jb.list_applications()
    db.create_database()

    for app in apps:
        details = jb.view_job(app['Job ID'])
        end = app['Last Day to Apply'] if len(app['Last Day to Apply']) > 0 else '01-JAN-1970'
        location = app['Work Location'] if 'Work Location' in app else ""
        db.add(app['Job ID'], app['Job Title'], app['Employer'], details['Description'], location, end, True)
