import sys
import json
import getpass
import argparse
import subprocess
from utils import open_os
from formatters import format
from operator import itemgetter
from jobminebrowser import JobmineBrowser, JobmineException, JobSearchQuery
from key import store_user_info, get_user_info, remove_user


def main(*args):
    """
    Command-line main interface for the Jobmine application.  Runs the application's parser and
    calls the JobmineBrowser accordingly.

    :args      List of command-line arguments, defaults to sys.argv if omitted
    :return    None
    """
    if len(args) == 0:
        args = sys.argv[1:]

    # Create and add the subparsers for the supported Jobmine methods;
    # parse the arguments based on the subparser
    parser = argparse.ArgumentParser(description='Command-line interface for the Jobmine python application.',
                                     prog='jobmine', epilog='Who would make such a thing?')
    subparsers = parser.add_subparsers(help='Sub-command menu', dest='command')

    change_user = subparsers.add_parser('change_user', help='change the default user')
    change_user.add_argument('--delete', action='store_true', default=False, help='delete the stored user')

    documents = subparsers.add_parser('documents', help='view/upload/list resumes')
    documents.add_argument('--list', action='store_true', default=False, help='list documents')
    documents.add_argument('--edit', nargs=2, metavar=('path', 'id'), help='reupload an existing resume')
    documents.add_argument('--upload', nargs=2, metavar=('path', 'name'), help='upload a new resume')
    documents.add_argument('--download', nargs=2, metavar=('id', 'document_type'), help='download specified document; types can be doc or package')
    documents.add_argument('--delete', nargs=1, metavar='id', help='delete the specified document')

    shortlist = subparsers.add_parser('shortlist', help='get shortlisted jobs')
    shortlist.add_argument('--add', nargs='?', help='job identifier for a job to add to your shortlist')

    interviews = subparsers.add_parser('interviews', help='get interviews')
    interviews.add_argument('interview', choices=('group', 'special', 'cancelled', 'normal'), default='normal',
                            help='specify which interviews to get, defaults to regular interviews.', nargs='?')

    applications = subparsers.add_parser('applications', help='Get applications')
    applications.add_argument('--inactive', action='store_false', default=True,
                              help='grab applications, specify whether to grab active or inactive (defaults to active).')

    search = subparsers.add_parser('jobs', help='search for jobs; all options are optional.')
    search.add_argument('--view', nargs='?', help='view the posting specified by the job id', dest='job_id')
    search.add_argument('--search', action='store_true', default=False, help='search for jobs')
    search.add_argument('--employer', help='string to match employer\'s name')
    search.add_argument('--title', help='string to match job title')
    search.add_argument('--location', help='string for the location of the job')
    search.add_argument('--term', help='the term to look for; one of (semester YYYY or the term number XXXX)')
    search.add_argument('--levels', help='the seniority of the position, defaults jr, int, sr',
                        choices=('jr', 'int', 'sr', 'bachelors', 'phd', 'masters'))
    search.add_argument('--status', help='the status of the job', choices=('approved', 'available', 'cancelled', 'posted'),
                        default='posted')
    search.add_argument('--disciplines', help='up to three programs for the jobs', nargs='*')
    search.add_argument('--limit', help='limit the number of results returned', default=None)

    arguments = vars(parser.parse_args(args))
    if arguments['command'] == 'change_user':
        # Only non-jobmine command; using the keypass set or delete
        # the user being used; only one user is allowed at a time.
        if arguments['delete']:
            username, _ = get_user_info()
            remove_user(username)
            print 'Deleted user %s' % username
        else:
            username = raw_input("Username: ")
            store_user_info(username, getpass.getpass("Password: "))
            print 'Default user is now %s' % username
    else:
        browser = JobmineBrowser()
        username, password = get_user_info()

        if username is None or password is None:
            print "No user data found.  Have you ran 'change_user'?"
            exit(1)

        try:
            browser.authenticate(username, password)
            command, result = arguments['command'], None
            if command == 'documents':
                if arguments['list']:
                    result = browser.list_documents()
                elif arguments['download']:
                    result = browser.download_document(arguments['id'], arguments['document_type'])
                    open_os(result)
                elif arguments['delete']:
                    browser.delete_document(int(arguments['delete'][0]))
                    result = 'Successfully deleted the document.'
                elif arguments['upload']:
                    browser.upload_document(path=arguments['upload'][0], name=arguments['upload'][1])
                    result = 'Succesfully uploaded new resume.'
                elif arguments['edit']:
                    browser.upload_document(path=arguments['edit'][0], existing=int(arguments['edit'][1]))
                    result = 'Successfully reuploaded resume.'
            elif command == 'jobs':
                if arguments['job_id']:
                    result = browser.view_job(arguments['job_id'])
                elif arguments['search']:
                    filter_keywords = {}
                    for job_filter in JobSearchQuery.filters:
                        if arguments[job_filter] is not None:
                            filter_keywords[job_filter] = arguments[job_filter]
                    result = browser.list_jobs(filters=filter_keywords,
                                               limit=int(arguments['limit']) if arguments['limit'] else None)
            elif command == 'applications':
                result = browser.list_applications(active=arguments['inactive'])
            elif command == 'interviews':
                result = browser.list_interviews(interview=arguments['interview'])
            elif command == 'shortlist':
                if arguments['add']:
                    result = browser.add_to_shortlist(arguments['add'])
                else:
                    result = browser.list_shortlist()
            # Print out the result formatted based on the type of data returned
            format(result)
        except JobmineException as e:
            # Jobmine exception usually means that Jobmine is down, format the string
            # in a printable manner for the user
            print "Error: %s" % e

    return None
