#!/usr/bin/env python
# -*- coding: utf-8 -*-
# resultssubmitter.py
"""Submit test results to a QATrack+ Server."""
# Copyright (c) 2015 Aditya Panchal
# Portions taken from a thread from the QATrack+ discussion group:
# https://groups.google.com/d/topic/qatrack/vO5H-zsfgsc/discussion

import requests
import logging
logger = logging.getLogger('qatrackimport.resultssubmitter')


class ResultsSubmitter(object):
    """Class that will submit test results to a QATrack+ Server."""
    def __init__(self, url, username, password):

        self.url = url
        self.username = username
        self.password = password

        # Set up a requests session
        self.session = requests.Session()

        self.login()

    def login(self):
        """Login to the QATrack+ server."""

        # HTTP GET the login page to retrieve the CSRF token
        login_url = self.url + "accounts/login/"
        self.session.get(login_url)
        self.token = self.session.cookies['csrftoken']

        login_data = {
            'username': self.username,
            'password': self.password,
            'csrfmiddlewaretoken': self.token
        }

        # Perform the login
        r = self.session.post(login_url, data=login_data)
        logger.debug("URL: %s Headers: %s Status code: %s",
                     r.url, r.headers, r.status_code)

    def submit_data(self, utc, test_results):
        """Submit the test results to the server."""

        # URL of UnitTestCollection (UTC) that is to be performed
        test_list_url = self.url + "qa/utc/perform/" + str(utc) + "/"

        test_results['csrfmiddlewaretoken'] = self.token
        logger.debug("Test results: %s", test_results)

        # Submit test data
        r = self.session.post(test_list_url, data=test_results)
        logger.debug("URL: %s Headers: %s Status code: %s",
                     r.url, r.headers, r.status_code)

        # Return the response text
        return r.text

if __name__ == '__main__':

    import sys
    import argparse
    import datetime
    import logging
    import logging.handlers
    logger = logging.getLogger('qatrackimport')
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(ch)

    # Set up argparser to parse the command-line arguments
    class DefaultParser(argparse.ArgumentParser):
        def error(self, message):
            sys.stderr.write('error: %s\n' % message)
            self.print_help()
            sys.exit(2)

    parser = DefaultParser(
        description="Submit test results to a QATrack+ Server.")
    parser.add_argument("--url",
                        help="QATrack+ Server URL")
    parser.add_argument("-u", "--username",
                        help="Username")
    parser.add_argument("-p", "--password",
                        help="Password")
    parser.add_argument("-utc",
                        help="Unit Test Collection number",
                        type=int)
    parser.add_argument("-n", "--numforms",
                        help="Number of form values",
                        type=int)
    parser.add_argument("-o", "--output",
                        help="File to save the resulting HTML response")
    parser.add_argument("-d", "--debug",
                        help="Show debug log",
                        action="store_true")

    args = parser.parse_args()

    # Set some defaults
    url = "http://127.0.0.1:8000/" if (args.url is None) else args.url
    username = 'admin' if (args.username is None) else args.username
    password = 'admin' if (args.password is None) else args.password
    utc = 1 if (args.utc is None) else args.utc
    numforms = 1 if (args.numforms is None) else args.numforms

    # Set debug logging if the debug flag is set
    if args.debug:
        logger.setLevel(logging.DEBUG)

    dt = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")

    test_results = {
        "work_started": dt,
        "work_completed": "",
        "status": 2,  # Approved status
        "form-TOTAL_FORMS": str(numforms),
        "form-INITIAL_FORMS": str(numforms),
        "form-MAX_NUM_FORMS": "1000",
    }

    # Create the test results
    for n in xrange(numforms):
        test_results["form-" + str(n) + "-value"] = "1"

    # Submit the results
    rs = ResultsSubmitter(url, username, password)
    text = rs.submit_data(utc, test_results)

    # Write out the response text if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write(text)
