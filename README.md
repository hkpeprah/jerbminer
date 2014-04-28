Jerbminer (Jobmine Miner)
=========================
Jerbminer provides a script (and GUI application) for interfacing with the University of Waterloo's Jobmine system.  *Jobmine* is a web application developed by the University of Waterloo to help students with the coop process.  This script/application is in no way affiliated with the University of Waterloo and is the side project of one student.

## Installation
* **Local**: `pip install Jerbminer.tar.gz`
* **Global**: `sudo pip install Jerbminer.tar.gz`

## Usage
`Usage: jobmine command [arguments....]`

**Example**: `jobmine jobs --search --location "United States" --disciplines "Computer Science" "Software" --term 1149` will return all the Computer Science and/or Software Engineering jobs that have been posted for Fall 2014 coop and are located in the United States.

| Command         | Description                        | Arguments                    | Description                                   |
| --------------- | ---------------------------------- | ---------------------------- | --------------------------------------------- |
| change_user     | Change current Jobmine user.       | (no argument)                | Change the Jobmine user in the keyring.       |
|                 |                                    | --delete                     | Remove the Jobmine user from the keyring.     |
| documents       | View, upload or list documents.    | --list                       | List all documents.                           |
|                 |                                    | --download ID {package, doc} | Download the specified package or resume.     |
|                 |                                    | --upload PATH NAME           | Upload a new resume specified by the path.    |
|                 |                                    | --delete ID                  | Deleted the specified document (`ID >= 1`)      |
|                 |                                    | --edit PATH ID               | Reupload the specified document (`ID >= 1`)     |
| shortlist       | View or shortlist jobs.            | (no argument)                | List all shortlisted jobs.                    |
|                 |                                    | --add JOB_ID                 | Add specified job by job id to shortlist.     |
| interviews      | Get your interviews.               | (no argument)                | Return all normal interviews.                 |
|                 |                                    | {group, special, cancelled}  | Return group/special/cancelled interviews.    |
| applications    | List your applications.            | (no argument)                | Return list of active applications.           |
|                 |                                    | --inactive                   | Return list of inactive applications.         |
| jobs            | Search, view, apply for jobs.      | --view JOB_ID                | View the specified job information.           |
|                 |                                    | --search                     | Search for jobs.  Add filters from below.     |
|                 |                                    | --location LOCATION          | Location of the job.                          |
|                 |                                    | --employer EMPLOYER          | Name of the employer.                         |
|                 |                                    | --title TITLE                | Job title.                                    |
|                 |                                    | --disciplines DISCIPLINES... | Up to three programs to filter on.            |
|                 |                                    | --status {approved, ...}     | Status of the job; approved/posted/available/cancelled. |
|                 |                                    | --levels {jr, sr, int, ....  | Level of the position, such as `sr` for senior. |
|                 |                                    | --term TERM                  | The term to search for, like `1149` / `Fall 2014` |
|                 |                                    | --limit LIMIT                | Number of results to limit the search to.     |

## Package
This package/module provides the following utilities:

* **JobmineBrowser** - Browser for Jobmine
* **JobSearchQuery** - A query search for jobs.
* **Programs** - The coop programs.

**Example**:

```
from jobmine import JobmineBrowser

browser = JobmineBrowser()
browser.authenticate(username="george", password="costanza")
interviews = browser.list_interviews()
if len(interviews) > 0:
    print "I'm back baby!"
else:
    print "I like sports...I could do something in sports..."
```
