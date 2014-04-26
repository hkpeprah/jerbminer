import sys
import json
import getpass
import argparse
from operator import itemgetter
from jobminebrowser import JobmineBrowser, JobmineException
from key import store_user_info, get_user_info, remove_user


def main(*args):
    """
    Command-line main interface for the Jobmine application.  Runs the application's parser and
    calls the JobmineBrowser accordingly.

    :args               List of command-line arguments, defaults to sys.argv if omitted
    :return             None
    """
    if len(args) == 0:
        args = sys.argv[1:]

    # Create and add the subparsers for the supported Jobmine methods;
    # parse the arguments based on the subparser
    parser = argparse.ArgumentParser(description='Command-line interface for the Jobmine python application.',
                                     prog='jobmine', epilog='Who would make such a thing?')
    subparsers = parser.add_subparsers(help='Sub-command menu', dest='command')

    change_user = subparsers.add_parser('change_user', help='Change the default user')
    change_user.add_argument('--delete', action='store_false', default=False, help='Delete the stored user.')

    documents = subparsers.add_parser('resumes', help='View/upload/list resumes')

    shortlist = subparsers.add_parser('shortlist', help='Get shortlisted jobs')

    interviews = subparsers.add_parser('interviews', help='Get interviews')
    interviews.add_argument('--interview', choices=('group', 'special', 'cancelled', 'normal'), default='normal',
                            help='Specify which interviews to get, defaults to regular interviews.', nargs='?')

    applications = subparsers.add_parser('applications', help='Get applications')
    applications.add_argument('--active', action='store_false', default=True,
                              help='Grab applications, specify whether to grab active or inactive (defaults to active).')

    search = subparsers.add_parser('jobs', help='Search for jobs.  All options are optional of course.')
    search.add_argument('--view', nargs='?', help='view the posting specified by the job id', dest='job_id')
    search.add_argument('--employer', help='string to match employer\'s name')
    search.add_argument('--title', help='string to match job title')
    search.add_argument('--location', help='string for the location of the job')
    search.add_argument('--term', help='the term to look for; one of (semester YYYY or the term number XXXX)')
    search.add_argument('--levels', help='the seniority of the position, defaults jr, int, sr',
                        choices=('jr', 'int', 'sr', 'bachelors', 'phd', 'masters'))
    search.add_argument('--status', help='the status of the job', choices=('approved', 'available', 'cancelled', 'posted'),
                        default='posted')
    search.add_argument('--disciplines', help='up to three programs for the jobs', nargs='*')

    arguments = vars(parser.parse_args(args))
    if arguments['command'] == 'change_user':
        # Only non-jobmine command; using the keypass set or delete
        # the user being used; only one user is allowed at a time.
        if arguments['delete']:
            username, _ = get_user_info()
            remove_user(username)
            print 'Deleted user %s' % username
        else:
            store_user_info(raw_input("Username: "), getpass.getpass("Password: "))
    else:
        browser = JobmineBrowser()
        username, password = get_user_info()

        if username is None or password is None:
            raise Exception("No user data found.  Have you ran 'change_user'?")

        try:
            browser.authenticate(username, password)
            if 'job_id' in arguments and arguments['job_id']:
                command = 'view_%s' % arguments['command'][:-1]
            else:
                command = 'list_%s' % arguments['command']
            result = getattr(browser, command)(**arguments)

            if isinstance(result, list):
                # Implicit assumping that allow lists returned are list of dictionaries
                # to be printed in a table.
                if len(result) == 0:
                    print "No results found."
                else:
                    print format_as_table(result, result[0].keys(), result[0].keys()).rstrip()
            elif isinstance(result, dict):
                print format_as(result)
            else:
                print result
        except JobmineException as e:
            print "Error: %s" % e

    return None


def format_as(data, keys=None, sort_by_key=None, sort_order_reverse=False):
    """
    """
    output = ""
    for index, (key, value) in enumerate(data.iteritems()):
        if isinstance(value, list):
            value = ", ".join(value)
        output += "{0}:\n{1}".format(key.title().replace(':', ''), value)
        output += "\n" if index == len(data) - 1 else "\n\n"

    return output


def format_as_table(data, keys, header=None, sort_by_key=None, sort_order_reverse=False):
    """Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.

    Source: http://www.calazan.com/python-function-for-displaying-a-list-of-dictionaries-in-table-format/

    Required Parameters:
        data - Data to process (list of dictionaries). (Type: List)
        keys - List of keys in the dictionary. (Type: List)

    Optional Parameters:
        header - The table header. (Type: List)
        sort_by_key - The key to sort by. (Type: String)
        sort_order_reverse - Default sort order is ascending, if
            True sort order will change to descending. (Type: Boolean)
    """
    # Sort the data if a sort key is specified (default sort order
    # is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=itemgetter(sort_by_key),
                      reverse=sort_order_reverse)

    # If header is not empty, add header to data
    if header:
        # Get the length of each header and create a divider based
        # on that length
        header_divider = []
        for name in header:
            header_divider.append('-' * len(name))

        # Create a list of dictionary from the keys and the header and
        # insert it at the beginning of the list. Do the same for the
        # divider and insert below the header.
        header_divider = dict(zip(keys, header_divider))
        data.insert(0, header_divider)
        header = dict(zip(keys, header))
        data.insert(0, header)

    column_widths = []
    for key in keys:
        column_widths.append(max(len(str(column[key])) for column in data))

    # Create a tuple pair of key and the associated column width for it
    key_width_pair = zip(keys, column_widths)

    format = ('%-*s     ' * len(keys)).strip() + '\n'
    formatted_data = ''
    for element in data:
        data_to_format = []
        # Create a tuple that will be used for the formatting in
        # width, value format
        for pair in key_width_pair:
            data_to_format.append(pair[1])
            data_to_format.append(element[pair[0]])
        formatted_data += (format % tuple(data_to_format))
    return formatted_data
