import sys
import json
import getpass
import argparse
from utils import open_os
from formatters import format
from operator import itemgetter
from jobminebrowser import JobmineBrowser, JobmineException, JobSearchQuery
from key import store_user_info, get_user_info, remove_user


def parse_arguments(args):
    """
    Creates the subparser for the jobmine-cli application and parses the command-line
    arguments.
    """
    # Create and add the subparsers for the supported Jobmine methods;
    # parse the arguments based on the subparser
    parser = argparse.ArgumentParser(description='Command-line interface for the Jobmine python application.',
                                     prog='jobmine', epilog='Who would make such a thing?')
    subparsers = parser.add_subparsers(help='Sub-command menu', dest='command')

    user = subparsers.add_parser('user', help='jobmine cli user utilities')
    user.add_argument('--delete', action='store_true', default=False, help='delete the stored user')
    user.add_argument('--change', action='store_true', default=False, help='change the default user')

    documents = subparsers.add_parser('documents', help='view/upload/list resumes')
    documents.add_argument('--list', action='store_true', default=False, help='list documents')
    documents.add_argument('--edit', nargs=2, metavar=('path', 'id'), help='reupload an existing resume')
    documents.add_argument('--upload', nargs=2, metavar=('path', 'name'), help='upload a new resume')
    documents.add_argument('--download', nargs=2, metavar=('id', 'document_type'), help='download specified document; types can be doc or package')
    documents.add_argument('--delete', nargs=1, metavar='id', help='delete the specified document')

    shortlist = subparsers.add_parser('shortlist', help='get shortlisted jobs')
    shortlist.add_argument('--add', nargs=1, metavar='job_id', help='pass job identifier for a job to add to your shortlist')
    shortlist.add_argument('--remove', nargs=1, metavar='job_id', help='pass job identifier for a job to remove from your shortlist')
    shortlist.add_argument('--status', nargs='?', metavar='status', help='status of the job', default='posted',
                           choices=('approved', 'available', 'cancelled', 'posted'))

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

    opts = vars(parser.parse_args(args))
    if opts['command'] == 'user':
        if opts['delete']:
            username, _ = get_user_info()
            remove_user(username)
            return 'Deleted user %s' % username
        elif opts['change']:
            username = raw_input("Username: ")
            store_user_info(username, getpass.getpass("Password: "))
            return 'Default user is now %s' % username
        else:
            return user.format_help() 
    else:
        browser = JobmineBrowser()
        username, password = get_user_info()

        if username is None or password is None:
            raise JobmineException("No user found.  Have you run 'user --add'?")

        browser.authenticate(username, password)
        if opts['command'] == 'documents':
            if opts['list']:
                return browser.list_documents()
            elif opts['download']:
                path = browser.download_document(*opts['download'])
                open_os(path)
                return path
            elif opts['delete']:
                return browser.delete_document(int(opts['delete'][0]))
            elif opts['upload']:
                return browser.upload_document(path=opts['upload'][0],
                                               name=opts['upload'][1])
            elif opts['edit']:
                return browser.upload_document(path=opts['edit'][0],
                                               existing=int(opts['edit'][1]))
        elif opts['command'] == 'applications':
            return browser.list_applications(active=opts['inactive'])
        elif opts['command'] == 'interviews':
            return browser.list_interviews(interview=opts['interview'])
        elif opts['command'] == 'shortlist':
            if opts['add']:
                return browser.add_to_shortlist(opts['add'][0], filters={
                    'status': opts['status']
                })
            elif opts['remove']:
                return browser.remove_from_shortlist(opts['remove'][0])
            return browser.list_shortlist()
        elif opts['command'] == 'jobs':
            if opts['job_id']:
                return browser.view_job(opts['job_id'])
            elif opts['search']:
                filters = dict((query, opts[query]) for query in JobSearchQuery.filters if \
                               opts[query] is not None)
                limit = int(opts['limit']) if opts['limit'] else None
                return browser.list_jobs(filters=filters,
                                          limit=limit)
        else:
            return parser.format_help() 


def main(*args):
    """
    Command-line main interface for the Jobmine application.  Runs the application's parser and
    calls the JobmineBrowser accordingly.

    :args      List of command-line arguments, defaults to sys.argv if omitted
    :return    None
    """
    try:
        args = sys.argv[1:] if len(args) == 0 else args
        result = parse_arguments(args)
        print format(result if result is not None else 'Success')
    except JobmineException as e:
        print 'Error: %s' % e
        exit(1)
