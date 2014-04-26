import re
import json
import urllib
import difflib
import urlparse
import tempfile
import requests
import itertools
import mechanize
import anonbrowser
from bs4 import BeautifulSoup
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict


class JobmineException(Exception):
    pass


class JobmineBrowser(anonbrowser.AnonBrowser):
    """
    JobmineBrwoser is an instance of AnonBrowser used for interacting with Jobmine.

    :BASE_URL        The base url format for the jobmine site
    :FOLDER_URL      Jobmine loads content into iframes, theis i the format url
    :ENDPOINTS       Dictionary of endpoints
    """
    BASE_URL = 'https://jobmine.ccol.uwaterloo.ca/psp/SS/EMPLOYEE/WORK/{0}'
    FOLDER_URL = 'https://jobmine.ccol.uwaterloo.ca/psc/SS/EMPLOYEE/WORK/c/UW_CO_STUDENTS.{0}.GBL'
    CMD_URL = 'https://jobmine.ccol.uwaterloo.ca/psc/SS/'
    ENDPOINTS = {
        '*': "",
        'nav': "h/?tab=DEFAULT",
        'applications': "UW_CO_APP_SUMMARY",
        'shortlist': "UW_CO_JOB_SLIST",
        'interviews': "UW_CO_STU_INTVS",
        'profile': "UW_CO_STUDENT",
        'documents': "UW_CO_STU_DOCS",
        'rankings': "UW_CO_STU_RNK2",
        'jobs': "UW_CO_JOBSRCH",
        'details': "UW_CO_JOBDTLS"
    }

    def __init__(self, *args, **kwargs):
        """
        Jobmine's refresh headers aren't handle properply by mechanize, so
        we ignore them.
        """
        anonbrowser.AnonBrowser.__init__(self, cookiefile='/tmp/jobmine.cookies')
        self.set_handle_redirect(True)
        self.set_handle_refresh(False)
        self.set_handle_redirect(mechanize.HTTPRedirectHandler)

    def _get_jobs(self, limit=None, filters=None, extract=None):
        """
        Private method that performs the job search inquiry.  Returns a generator function to get results,
        further calls will paginate.

        :limit      Integer, limit the responses to return
        :filters    Optional dictionary of job search filters
        :extract    Optional function to get a matched job
        :return     Generator
        """
        if not filters:
            filters = {}

        regex = re.compile(r'.*trUW_CO_JOBRES_VW\$[0-9]+_row[0-9]+')
        response = self.open(self.FOLDER_URL.format(self.ENDPOINTS['jobs'])).read()
        query = JobSearchQuery()

        self.select_form(nr=0)
        # These tokens we have to grab from the page as they change, pagination requires
        # the state number.
        paginating, rows = True, []
        required_tokens = ['ICSID', 'ICStateNum']
        for token in required_tokens:
            control = next(control for control in self.form.controls if control.name == token)
            query.add(token, control.value)
        self.submit()

        while paginating:
            form_post_url = query.make_query(self.geturl(), **filters)
            response = self.open_novisit(form_post_url).read()
            soup = BeautifulSoup(response)

            # Need the headers in order to construct the dictionary so find the headers
            # relative to the rows
            body = list(soup.findAll('tr', id=regex))[0].parent.parent
            headers = map(lambda tag: tag.text.strip(), list(body.findAll('th')))

            # Find the rows matching the regex and and get the text
            found = list(map(lambda tag: tag.text.strip(), row.findAll('td')) for \
                         row in soup.findAll('tr') if isinstance(row.attrs.get('id', None), basestring) and \
                         regex.match(row.attrs.get('id')))

            duplicates = not next((row for row in found if row not in rows), False)
            if duplicates or len(found) == 0:
                # If no results or if it matches the last found row, pagination
                # has finished.
                raise StopIteration

            jobs = map(lambda row: OrderedDict(zip(headers, row)), found)
            if extract:
                filtered = filter(extract, jobs)
                if len(filtered) >= 1:
                    query.row = len(rows) + jobs.index(filtered[0])
                    yield filtered[0], query
                    break
                query.paginate()
                continue
            elif isinstance(limit, int) and len(found) + len(rows) >= limit:
                limit -= len(rows)
                yield (rows + jobs[:limit])
                break
            elif jobs[0]['Job Title'] == 'No Matches Found':
                return
                yield []

            rows += found
            query.paginate()
            yield jobs

        raise StopIteration

    def _download_document(self, id, document_type):
        """
        Backhand method called for download documents.  Jobmine redirects three times before
        actually downloading the document; there are two types of files 'doc' (resume) and 'package'.

        :id               String, the document number (1 to number of documents)
        :document_type    One of 'doc' or 'package'
        :return           String
        """
        ic_action = 'UW_CO_PDF_LINKS_UW_CO_{0}_VIEW${1}'
        download_url = self.FOLDER_URL.format(self.ENDPOINTS['documents'])
        document = next((index for index, document in enumerate(self.list_documents()) if document['Document Number'] == str(id)), None)

        if document is not None:
            # Generates the page with the JS that generates the download url; server-sided
            # generation
            download_url += "?ICAction={0}".format(ic_action.format(document_type.upper(), document))
            response = self.open_novisit(download_url).read()

            query, index = '', response.index('cmd=viewattach')
            while response[index] not in '\'"?,()':
                query += response[index]
                index += 1

            # Fetch the actual document from the download command url
            response = self.open_novisit(self.CMD_URL + '?{0}'.format(query)).read()
            # Since this page sets a refresh header, it's not the actual pdf yet..
            pdf = self.open_novisit(response.split('\n')[3]).read()

            return pdf

    def post(self, url, data):
        """
        Posts data to the specified url.

        :url       The url to post to
        :data      Dictionary of form data
        :return    String
        """
        response = requests.post(url, data=data, cookies=self.cookie_jar, headers={
            'User-Agent': 'Mozilla/5.0'
        })

        return response.content
        
    def authenticate(self, username, password):
        """
        Authenticate the user and login.

        :username    String, user's Quest ID
        :password    String, user's Quest password
        :return      Boolean
        """
        login_url = self.BASE_URL.format(self.ENDPOINTS['*'], timeout=30.0)
        response = self.open(login_url)
        # ID/name of form fields are userid/pwd respectively for
        # username, password combination
        form_nr = 0
        while True:
            try:
                self.select_form(nr=form_nr)
                form_nr += 1
                self.form['userid'] = username
                self.form['pwd'] = password
                self.submit()
                break
            except mechanize._form.ControlNotFoundError:
                # Not the right form
                continue
            except mechanize._mechanize.FormNotFoundError:
                # No more forms available on page, authentication failed
                return False

        if 'errorCode=999' in self.geturl():
            raise JobmineException('Jobmine is currently closed.')

        self.save_cookies()
        return True

    def parse(self, endpoint, regex):
        """
        Parse the table pointed to by the endpoint.

        :endpoint    The folder to grab
        :regex       The pattern for getting the rows.
        :return      dict
        """
        regex = re.compile(regex)
        url = self.FOLDER_URL.format(self.ENDPOINTS[endpoint])
        response = self.open(url).read()
        soup = BeautifulSoup(response)

        # Find the rows matching the regex and and get the text
        rows = list(map(lambda tag: tag.text.strip() if len(tag.findAll('input')) == 0 else \
                        tag.findAll('input')[0]['value'], row.findAll('td')) for \
                        row in soup.findAll('tr', id=regex))

        if len(rows) == 0:
            return []

        # Need the headers in order to construct the dictionary so find the headers
        # relative to the rows
        body = list(soup.findAll('tr', id=regex))[0].parent.parent
        headers = map(lambda tag: tag.text.strip(), list(body.findAll('th')))

        # Find indices that are null; indices that are filled with empty strings as
        # Jobmine creates table rows with empty cells
        null_indices = list(index for index, text in enumerate(headers) if len(text) == 0)
        headers = list(text for index, text in enumerate(headers) if index not in null_indices)
        rows = list(list(text for index, text in enumerate(row) if index not in null_indices) for row in rows)

        if len(rows[0]) == 0:
            return []
        return map(lambda row: OrderedDict(zip(headers, row)), rows)

    def list_shortlist(self):
        """
        List the user's shortlisted jobs.

        :return    List of dictionaries
        """
        short_list = self.parse('shortlist', r'trUW_CO_STUJOBLST.*')
        return short_list

    def list_applications(self, active=False):
        """
        List the applications the user has made.

        :return    List of dictionaries
        """
        regex = 'tr.*UW_CO_APPS{0}.*'.format('V\$' if active else '_VW2')
        applications = self.parse('applications', regex)
        return applications

    def list_interviews(self, interview=None):
        """
        List the user's interviews, optionally filtered by the type.

        :interview    The type of interview
        :return       List of dictionaries
        """
        if interview == "group":
            regex = '.*trUW_CO_GRP_STU_V.*'
        elif interview == "special":
            regex = '.*trUW_CO_NSCHD_JOB\$.*'
        elif interview == "cancelled":
            regex = '.*UW_CO_SINT_CANC\$.*'
        else:
            regex = '.*trUW_CO_STUD_INTV\$.*'

        interviews = self.parse('interviews', regex)
        return interviews

    def list_profile(self):
        """
        List the user's profile.

        :return    List of dictionaries
        """
        profile = self.parse('profile', r'trUW_CO_STDTERMVW.*')
        return profile

    def list_documents(self):
        """
        List the user's resumes and packages.

        :return        List of dictionaries
        """
        resumes = self.parse('documents', r'trUW_CO_STU_DOCS.*')
        return resumes

    def download_document(self, id, document_type=None):
        """
        Downloads the specified document into a temporary file and returns the path
        to the tempfile.

        :id               String, the document number
        :document_type    One of 'package' or 'doc'
        :return           String
        """
        if not document_type:
            document_type = 'doc'
        elif document_type not in ['doc', 'package']:
            raise JobmineException('Unknown document type passed.')

        pdf = self._download_document(id, document_type)
        if pdf:
            os_handle, tmp = tempfile.mkstemp()
            tmp = '{0}.pdf'.format(tmp)
            with open(tmp, 'w') as output:
                output.write(pdf)

            return tmp

    def list_rankings(self):
        """
        List the user's job rankings.

        :return    String
        """
        rankings = self.parse('rankings', r'trUW_CO_STU_RNK.*')
        return rankings

    def view_job(self, job_id):
        """
        View the specified job.  Requires a valid job identifier that can be retrieved from
        a list of jobs.  Returns a dictionary of the job's data.

        :job_id    String representing the job id
        :return    String
        """
        url = self.FOLDER_URL.format(self.ENDPOINTS['details']) + "?UW_CO_JOB_ID={0}".format(job_id)
        response = self.open_novisit(url).read()
        soup = BeautifulSoup(response)
        content = soup.findAll('div', id='PAGECONTAINER')

        # Do some analyzation here to figure out what peices of content belong to what
        # from the raw string.
        raw = re.sub(r'\s\s+', '\n', content[0].text)
        information, description = raw.split('Job Description')
        information = information.split('\n')
        description = description.replace(u'\xa0', u' ').replace('\r', '\n').strip()

        # Parse the information on the page
        job_attributes = OrderedDict()
        while len(information) > 0:
            key, attributes = information.pop(0), []
            if ':' not in key:
                continue
            else:
                while len(information) > 0:
                    value = information.pop(0).replace(u'\xa0', u' ').strip()
                    if ':' in value:
                        information.insert(0, value)
                        break
                    elif len(value) > 0:
                        attributes.append(value)

            if len(attributes) == 0:
                job_attributes[key] = ""
            else:
                job_attributes[key] = attributes if len(attributes) > 1 else attributes[0]

        job_attributes['Description'] = description
        return job_attributes

    def add_to_shortlist(self, job_id, filters=None):
        """
        Shortlists a job specified by the ID, can optionally pass in filters to make the search go
        faster.

        :job_id     String, the job identifier
        :filters    Optional dictionary of job query filters
        :return     Boolean indicating success or failure of add
        """
        if not filters:
            filters = {}

        job, query = next(self._get_jobs(filters=filters, extract=lambda job: job['Job Identifier'] == job_id), 
                          (None, None))

        # Check that job has not been added to the shortlist
        if job is not None and job['Short List'] != 'On Short List':
            url = self.FOLDER_URL.format(self.ENDPOINTS['jobs']) + \
                  '?ICAction=UW_CO_SLIST_HL${0}&ICSID={1}&ICStateNum={2}'.format(query.row,
                                                                  query.get('ICSID'),
                                                                  str(int(query.get('ICStateNum')) + 1))
            response = self.open_novisit(url).read()
            return not('This page is no longer available' in response)

        return False

    def list_jobs(self, limit=None, filters=None):
        """
        Search and list jobs.  By passing in key word arguments, the user can specify how
        to filter the job search to narrow the results passed.

        :return    Dictionary
        """
        generators = [rows for rows in self._get_jobs(limit, filters=filters)]
        jobs = list(itertools.chain(*generators))

        if len(jobs) > 0:
            return jobs

        return []

class JobSearchQuery():
    """
    Creates a query for job searches by assigning values to the relevant hidden and visibile fields.
    """
    filters = [
        'employer',
        'title',
        'location',
        'term',
        'levels',
        'status',
        'disciplines'
    ]

    __data = {
        'ICAction': "UW_CO_JOBSRCHDW_UW_CO_DW_SRCHBTN",
        'ICNAVTYPEDROPDOWN': 1,
        'ICType': "Panel",
        'ICElementNum': 0,
        'ICXPos': 0,
        'ICYPos': 0,
        'ResponsetoDiffFrame': -1,
        'TargetFrameName': "None",
        'ICSaveWarningFilter': 0,
        'ICChanged': -1,
        'ICResubmit': 0,
    }

    def __init__(self, *args, **kwargs):
        self.clear()

    def clear(self):
        """
        Resets the job inquery data
        """
        self.data = {}
        self.__readable_data = {}
        self.status('posted')
        self.term('fall 2014')
        self.levels('jr', 'int', 'sr')
        self.location('')
        self.title('')
        self.employer('')
        self._data = self.__data.copy()

    def get(self, name):
        if name in self.__readable_data:
            return self.__readable_data[name]
        data = self.data.copy()
        data.update(self._data.copy())
        return data.get(name, None)

    def add(self, field, value):
        self.data[field] = value

    def readable(field):
        """
        """
        def wrap(function):
            def wrapped_function(instance, *args):
                name = function.__name__
                status = function(instance, field, *args)
                instance.__readable_data[name] = instance.data[field]
            return wrapped_function
        return wrap

    @readable('UW_CO_JOBSRCH_UW_CO_LOCATION')
    def location(self, field, location):
        self.data[field] = location

    @readable('UW_CO_JOBSRCH_UW_CO_JOB_TITLE')
    def title(self, field, name):
        self.data[field] = name

    @readable('UW_CO_JOBSRCH_UW_CO_EMPLYR_NAME')
    def employer(self, field, name):
        self.data[field] = name

    @readable('UW_CO_JOBSRCH_UW_CO_WT_SESSION')
    def term(self, field, name):
        # TODO: Unhardcode this...how to figure out names
        terms = {
            'fall 2013': 1139,
            'winter 2014': 1141,
            'spring 2014': 1145,
            'fall 2014': 1149
        }
        self.data[field] = terms.get(name.lower(), name)

    @readable('UW_CO_JOBSRCH_UW_CO_JS_JOBSTATUS')
    def status(self, field, name):
        statuses = {
            'approved': "APPR",
            'available': "APPA",
            'cancelled': "CANC",
            'posted': "POST"
        }
        self.data[field] = statuses.get(name.lower())

    def levels(self, *levels):
        field = 'UW_CO_JOBSRCH_UW_CO_COOP_{0}'
        for level in levels:
            formatted_field = field.format(level)
            self.data[field] = 'Y'
            self.data[field + '$chk'] = 'Y'

        self.__readable_data['levels'] = levels

    def disciplines(self, names):
        discipline = 'UW_CO_JOBSRCH_UW_CO_ADV_DISCP{0}'
        programs = []

        for index, name in enumerate(names):
            if index > 2:
                break
            self.data[discipline.format(index + 1)] = CoopPrograms.get_value(name)
            programs.append(name)

        self.__readable_data['disciplines'] = programs

    def paginate(self, down=False):
        if not 'ICStateNum' in self.data:
            return self

        state = int(self.data.get('ICStateNum'))

        if not down:
            self.data['ICStateNum'] = str(state + 1)
            self._data['ICAction'] = 'UW_CO_JOBRES_VW$hdown$0'
        else:
            self.data['ICStateNum'] = str(state - 1)
            self._data['ICAction'] = 'UW_CO_JOBRES_VW$hup$0'
        return self

    def make_query(self, url, *args, **kwargs):
        """
        Creates a url for fetching the query results (generated HTML page) by adding to the
        data to the respective form fields.

        :url       Base url to add query parameters to
        :return    String
        """
        for key, value in kwargs.iteritems():
            if hasattr(self, key):
                getattr(self, key)(value)

        serialized = self.data.copy()
        serialized.update(self._data)
        url = url + '?{0}'.format(urllib.urlencode(serialized))

        return url


class CoopPrograms():
    """
    List of programs you can search on Jobmine.
    """
    PROGRAMS = json.load(open('resources/majors.json', 'r'))

    @classmethod
    def get(cls, program, major = None, value=False):
        if major is not None:
            programs = cls.PROGRAMS.get(major)
        else:
            programs = []
            for faculty in cls.PROGRAMS.values():
                programs += faculty.items()
            programs = dict(programs)

        # Get the closest matching program to the on passed
        closest_match = difflib.get_close_matches(program, programs.keys())

        if value:
            return programs.get(closest_match[0])
        return closest_match

    @classmethod
    def get_value(cls, program, major=None):
        return cls.get(program, major, True)

    @classmethod
    def all(cls, major = None):
        if major is not None:
            return cls.PROGRAMS.get(major).keys()
        return itertools.chain(faculty.keys() for faculty in cls.PROGRAMS.values())
