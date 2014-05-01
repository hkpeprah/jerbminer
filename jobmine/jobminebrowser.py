import os
import re
import json
import urllib
import difflib
import requests
import urlparse
import tempfile
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

    def _get_tokens(self, tokens=None):
        """
        Get tokens from the currently selected form, if none is selected, then select
        the first one on the page.

        :tokens    A list of tokens to grab
        :return    List of tuples
        """
        if tokens is None:
            tokens = ['ICSID', 'ICStateNum']

        if not hasattr(self, 'form') or self.form is None:
            self.select_form(nr=0)

        return list((token, self.form[token]) for token in tokens)

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
        query, rows = JobSearchQuery(), []

        for token in self._get_tokens():
            query.add(*token)

        while True:
            form_post_url = query.make_query(self.geturl(), **filters)
            response = self.open_novisit(form_post_url).read()
            soup = BeautifulSoup(response)

            # Need the headers in order to construct the dictionary so find the headers
            # relative to the rows
            body = list(soup.findAll('tr', id=regex))[0].parent.parent
            headers = map(lambda tag: tag.text.encode('ascii', 'ignore').strip(),
                          list(body.findAll('th')))

            # Find the rows matching the regex and and get the text
            found = list(map(lambda tag: tag.text.encode('ascii', 'ignore').strip(), row.findAll('td')) for \
                         row in soup.findAll('tr') if isinstance(row.attrs.get('id', None), basestring) and \
                         regex.match(row.attrs.get('id')))

            if len(found) == 0 or found[0] in rows:
                # If no results or if it matches the last found row, pagination
                # has finished.
                break

            jobs = map(lambda row: OrderedDict(zip(headers, row)), found)
            if extract:
                filtered = filter(extract, jobs)
                if len(filtered) >= 1:
                    query.row = len(rows) + jobs.index(filtered[0])
                    yield filtered[0], query
                    break
                rows += found
            elif isinstance(limit, int) and len(found) + len(rows) >= limit:
                limit -= len(rows)
                yield (rows + jobs[:limit])
                break
            elif jobs[0]['Job Title'] == 'No Matches Found':
                return
                yield []
            else:
                rows += found
                yield jobs

            query.paginate()

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
        if isinstance(id, basestring):
            id = int(id)

        if id > 0 and id <= len(self.list_documents()):
            # Generates the page with the JS that generates the download url; server-sided
            # generation
            download_url += "?ICAction={0}".format(ic_action.format(document_type.upper(), str(id - 1)))
            response = self.open_novisit(download_url).read()

            # Fetch the actual document from the download command url
            query = re.search(r'(cmd=viewattach[^\'"\?,\(\)]+)', response).group(0)
            response = self.open_novisit(self.CMD_URL + '?{0}'.format(query)).read()
            # Since this page sets an improper refresh header, need to follow the header
            pdf = self.open_novisit(response.split('\n')[3]).read()

            return pdf

    def post(self, url, data, files=None):
        """
        Posts data to the specified url.

        :url       The url to post to
        :data      Dictionary of form data
        :files     Files (if any) to post
        :return    String
        """
        response = requests.post(url, data=data, cookies=self.cookie_jar, headers={
            'User-Agent': 'Mozilla/5.0'
        }, files=files)

        return response.content

    def save(self, url, tokens=None, extra_data=None):
        """
        Save the current transaction.

        :url           The url to save to
        :tokens        Optional list of tokens to attach to the request
        :extra_data    Extra dictionary of data to add to the request
        :return        Boolean
        """
        tokens = self._get_tokens() if tokens is None else tokens
        data = dict(tokens + [('ICAction', '#ICSave')])
        if extra_data is not None:
            data.update(extra_data)
        # Increase state number to trigger a change in state
        data['ICStateNum'] = str(int(data['ICStateNum']) + 1)
        response = self.open_novisit(url + "?{0}".format(urllib.urlencode(data))).read()

        return ('error' in response or 'not available' in response)

    def authenticate(self, username, password):
        """
        Authenticate the user and login.

        :username    String, user's Quest ID
        :password    String, user's Quest password
        :return      Boolean
        """
        login_url = self.BASE_URL.format(self.ENDPOINTS['*'], timeout=30.0)
        form_nr, response = 0, self.open(login_url)
        while True:
            # ID/name of form fields are userid/pwd respectively for
            # username, password combination
            try:
                # First form is not always the login form
                self.select_form(nr=form_nr)
                form_nr += 1
                self.form['userid'], self.form['pwd'] = username, password
                self.submit()
                self.save_cookies()
                break
            except mechanize._form.ControlNotFoundError:
                # Not the right form
                continue
            except mechanize._mechanize.FormNotFoundError:
                # No more forms available on page, authentication failed
                return False

        if 'errorCode=999' in self.geturl():
            raise JobmineException('Jobmine is currently closed.')

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
        soup = BeautifulSoup(self.open(url).read())

        # Find the rows matching the regex and and get the text
        rows = list(map(lambda tag: tag.text.encode('ascii', 'ignore').strip() if \
                        len(tag.findAll('input')) == 0 else tag.findAll('input')[0]['value'],
                        row.findAll('td')) for row in soup.findAll('tr', id=regex))

        if len(rows) == 0:
            return []

        # Need the headers in order to construct the dictionary so find the headers
        # relative to the rows
        body = list(soup.findAll('tr', id=regex))[0].parent.parent
        headers = map(lambda tag: tag.text.encode('ascii', 'ignore').strip(),
                      list(body.findAll('th')))

        # Find indices that are null; indices that are filled with empty strings as
        # Jobmine creates table rows with empty cells
        old_rows, rows = rows, [[] for _ in range(0, len(rows))]
        for index, header in zip(range(0, len(headers)), headers[:]):
            if index == 0:
                headers = []
            if len(header) == 0:
                continue # Null index
            headers.append(header)
            for j in range(0, len(rows)):
                rows[j].append(old_rows[j][index])

        if len(rows[0]) == 0:
            return []

        return map(lambda row: OrderedDict(zip(headers, row)), rows)

    def list_shortlist(self):
        """
        List the user's shortlisted jobs.

        :return    List of dictionaries
        """
        return self.parse('shortlist', r'trUW_CO_STUJOBLST.*')

    def list_applications(self, active=False):
        """
        List the applications the user has made.

        :return    List of dictionaries
        """
        return self.parse('applications',
                          'tr.*UW_CO_APPS%s.*' % ('V\$' if active else '_VW2'))

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
        # Filter to ensure there are actually interviews as Jobmine implicitly returns
        # a row of blank interviews.
        interviews = filter(lambda interview: len(list(itertools.chain(*interview.values()))) > 0,
                            interviews)
        return interviews

    def list_profile(self):
        """
        List the user's profile.

        :return    List of dictionaries
        """
        return self.parse('profile', r'trUW_CO_STDTERMVW.*')

    def list_documents(self):
        """
        List the user's resumes and packages.

        :return        List of dictionaries
        """
        return self.parse('documents', r'trUW_CO_STU_DOCS.*')

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

    def delete_document(self, document_number):
        """
        Deletes the specified document.  Document must exist for this to work.

        :document_number    The number of the document (1 to max number of documents)
        :return             None
        """
        documents = self.list_documents()
        if document_number <= 0 or document_number > len(documents):
            raise JobmineException('The specified document does not exist.')
        elif len(documents) == 1:
            raise JobmineException('Cannot delete document, atleast one must exist.')

        self.open(self.FOLDER_URL.format(self.ENDPOINTS['documents']))
        params = dict(self._get_tokens())
        params['ICAction'] = 'UW_CO_PDF_WRK_UW_CO_DOC_DELETE${0}'.format(document_number - 1)
        response = self.open(self.geturl() + "?{0}".format(urllib.urlencode(params))).read()

        if len(documents) == len(self.list_documents()):
            # If the length is the same as before, that mean something went wrong
            raise JobmineException('Document deletion failed.  Manually delete.')

    def upload_document(self, path, name=None, existing=None):
        """
        Upload the document pointed to by the path as a new document on Jobmine,
        document number should be in range(1, max number of documents)

        :path        Path to the file to upload (relative or absolute)
        :name        Optional name to give the uploaded file
        :existing    Optional existing id to reupload an existing document
        :return      None
        """
        documents = self.list_documents()
        upload = (existing if existing else len(documents)) - 1
        base_url = self.FOLDER_URL.format(self.ENDPOINTS['documents'])
        soup = BeautifulSoup(self.open(base_url).read())
        self.select_form(nr=0)

        # Need two tokens for a submission; statenum and icsid
        if existing is not None:
            if not(existing > 0 and existing <= len(documents)):
                raise JobmineException('The specified document does not exist.')
        else:
            # Create a new resume by posting to the create url; check to ensure
            # not exceeding the number of allowed documents
            create = 'UW_CO_PDF_WRK_UW_CO_DOC_CREATE'
            if len(soup.findAll('a', id=create)) == 0:
                raise JobmineException('Maximum document count reached.')
            url, tokens = self.geturl(), self._get_tokens()
            data = dict(tokens + [('ICAction', create)])

            # Create new document, save it and check for success
            response = self.open(self.geturl() + "0?{0}".format(urllib.urlencode(data))).read()
            save_status = self.save(url, tokens)
            if save_status and upload == len(self.list_documents()) - 1:
                raise JobmineException('Document create failed.  Manually upload.')
            else:
                upload += 1
                self.open(base_url)
                self.select_form(nr=0)

        # If a name exists, add it to the form
        if name is not None:
            description = 'UW_CO_STU_DOCS_UW_CO_DOC_DESC${0}'.format(upload)
            self.form[description] = name
            self.save(self.geturl(), extra_data=dict([(description, name)]))

        # Navigate to the form edit page
        params = dict(self._get_tokens())
        params['ICAction'] = 'UW_CO_PDF_WRK_UW_CO_DOC_ADD${0}'.format(upload)
        response = self.open(base_url + "?{0}".format(urllib.urlencode(params))).read()

        # File is uploaded as application/octet-stream
        self.select_form(nr=0)
        self.form.add_file(open(
            os.path.expanduser(
                os.path.expandvars(path)), 'rb'), 'application/pdf', os.path.split(path)[-1])
        response = self.submit().read()

        # Uploading failed if either of these exist in our response
        if 'error' in response or 'not available' in response:
            raise JobmineException('Document upload failed.  Manually upload.')

    def list_rankings(self):
        """
        List the user's job rankings.

        :return    String
        """
        return self.parse('rankings', r'trUW_CO_STU_RNK.*')

    def view_job(self, job_id):
        """
        View the specified job.  Requires a valid job identifier that can be retrieved from
        a list of jobs.  Returns a dictionary of the job's data.

        :job_id    String representing the job id
        :return    String
        """
        url = self.FOLDER_URL.format(self.ENDPOINTS['details']) + "?UW_CO_JOB_ID={0}".format(job_id)
        soup = BeautifulSoup(self.open_novisit(url).read())
        content = soup.findAll('div', id='PAGECONTAINER')

        # Do some analyzation here to figure out what peices of content belong to what
        # from the raw string.
        raw = re.sub(r'\s\s+', '\n', content[0].text)
        information, description = raw.split('Job Description')

        # Strip out empty whitespace lines and replace return carriages
        description = description.encode('ascii', 'ignore').replace('\r', '\n')
        description = '\n'.join(filter(lambda s: re.match(r'[\-_0-9A-Za-z]+', s),
                                       description.split('\n')))

        # Parse the information on the page by finding key-value pairs denoted by headers that
        # contain a colon
        regex = re.compile(r"""
            ([\s\w\-,\#]+        # matches a value for the field
             :                   # if colon, this is a key
             (?:\n+)             # non-capturing newline
            [\w\s\-,\#]+         # matches a value for the field
            (?:\n+))             # non-matching newline
        """, re.VERBOSE)
        job_information = OrderedDict((key.strip(), val.strip()) for (key, val) in \
                                      map(lambda d: d.split(':'), re.findall(regex, information)))
        job_information['Description'] = description
        return job_information

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

    def remove_from_shortlist(self, job_id):
        """
        Removes the job with the specified job id from the user's shortlist.

        :job_id    String, the job identifier
        :return    Boolean
        """
        remove = 'UW_CO_STUJOBLST$delete${0}$$0'
        shortlisted_jobs = self.list_shortlist()
        for index, job in enumerate(shortlisted_jobs):
            if job['Job Identifier'] == job_id:
                tokens = dict(self._get_tokens())
                url = self.FOLDER_URL.format(self.ENDPOINTS['shortlist']) + \
                      '?ICAction=UW_CO_STUJOBLST$delete${0}$$0&ICSID={1}&ICStateNum={2}'.format(index,
                                                                                                tokens['ICSID'],
                                                                                                tokens['ICStateNum'])
                response = self.open_novisit(url).read()
                self.save(self.geturl())
                if len(self.list_shortlist()) == len(shortlisted_jobs):
                    raise JobmineException('Something went wrong, manually remove.')
                return True

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
        Wraps a query param to provide a readable name for the field.
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


class Jobmine(JobmineBrowser):
    """
    Reference to the browser under the name of Jobmine.
    """
    pass


class CoopPrograms():
    """
    List of programs you can search on Jobmine.
    """
    PROGRAMS = json.load(
        open(
            os.path.join(
                os.path.dirname(__file__),
                'resources', 'majors.json'), 'r'))

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
