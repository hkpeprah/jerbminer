import time
from jobmine import JobmineBrowser
from jobmine.key import get_user_info


if __name__ == "__main__":
    interviews = []
    browser = JobmineBrowser()

    # Note: get_user_info only works if we've saved a Jobmine user
    browser.authenticate(*get_user_info())
    while True:
        # Poll every ten minutes for new interviews
        new_interviews = browser.list_interviews()
        if len(new_interviews) == 0:
            print "No interviews."
        else:
            for interview in new_interviews:
                if interview not in interviews:
                    print "New interview for %s at %s" % (interview['Job Title'], interview['Employer Name'])
                    interviews.append(interview)

        time.sleep(600)
