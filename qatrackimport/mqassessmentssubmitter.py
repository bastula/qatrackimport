#!/usr/bin/env python
# -*- coding: utf-8 -*-
# mqassessmentssubmitter.py
"""Read and submit assessment results from MosaiQ."""
# Copyright (c) 2015 Aditya Panchal

import resultssubmitter
import datetime
import pymssql
from operator import itemgetter
import pprint
import logging
logger = logging.getLogger('qatrackimport.mqassessmentssubmitter')

dtformat = "%Y%m%d"


class MQAssessmentsSubmitter(object):
    """Class that reads assessments from the MosaiQ DB and
       submits them to QATrack+"""
    def __init__(self, server=None, username=None, password=None):

        self.server = server
        self.username = username
        self.password = password
        self.qat_url = "http://127.0.0.1:8080/"
        self.qat_username = 'admin'
        self.qat_password = 'admin'

        # Connect to the MosaiQ database
        self.connect_to_database()

    def set_qatrack_server(self, url, username, password):
        """Setup the QA Track+ server settings."""

        self.qat_url = url
        self.qat_username = username
        self.qat_password = password

    def connect_to_database(self):
        """Connect to the MosaiQ database."""

        logger.info("Connecting to MosaiQ database...")
        self.conn = pymssql.connect(
            self.server, self.username, self.password, "MOSAIQ")
        self.cursor = self.conn.cursor()

    def disconnect_from_database(self):
        """Disconnect from the the MosaiQ database."""

        self.conn.close()

    def get_mosaiq_obsreq(self, viewid, startdate=None, enddate=None,
                          patientid=None):
        """Get a list of MosaiQ ObsReq instances for the given
           observation view definition."""

        startdate = "19010101" if startdate is None else startdate
        # Query from startdate to enddate + 1 since endtime is set to midnight
        query = """SELECT OBR_Set_ID, Create_DtTm FROM ObsReq
                   WHERE VIEW_OBD_ID LIKE %s
                   AND Create_DtTm >= CONVERT(datetime, %d)
                   """
        if enddate is not None:
            query += \
                """AND Create_DtTm <= DATEADD(day, 1, CONVERT(datetime, %d))"""

        if patientid is not None:
            query = query + " AND Pat_ID1 LIKE " + str(patientid)
        query = query + ";"
        logger.debug("Start date: %s End date: %s", startdate, enddate)
        logger.debug("Obsreq Query: %s", query)
        self.cursor.execute(query, (viewid, startdate, enddate))
        obsreqs = list(self.cursor.fetchall())
        return sorted(obsreqs, key=itemgetter(1))

    def get_mosaiq_obsset(self, setid):
        """Get a set of MosaiQ observation instances for the given
           observation set ID."""

        query = """SELECT OBX_ID, OBR_Set_ID, Pat_ID1, OBD_ID,
                   Obs_Float, Obs_String FROM Observe WHERE
                   OBR_SET_ID LIKE %s;"""
        self.cursor.execute(query, setid)
        return self.cursor.fetchall()

    def convert_test_result(self, data, mapping, date):
        """Convert the test result into a dictonary compatible with the
           QATrack+ UnitTestCollection."""

        # Create the test results set
        test_results = {}
        for x in data:
            logger.debug('Test: %s', x)
            if str(x[3]) in mapping:
                m = mapping[str(x[3])]
                key = "form-" + str(m[0]) + "-value"
                if "bool" in str(m[1]):
                    test_results[key] = int(x[4])
                elif "float" in str(m[1]):
                    test_results[key] = x[4]
                elif "str" in str(m[1]):
                    test_results[key] = x[5].rstrip()

        logger.debug('Mapping: %s', pprint.pformat(mapping))
        logger.debug('Test Results without skips: %s',
                     pprint.pformat(test_results))

        # Add the skipped items
        for k, m in mapping.items():
            if not "form-" + str(m[0]) + "-value" in test_results:
                test_results["form-" + str(m[0]) + "-skipped"] = "1"

        # Insert operator and approval initials and comments
        comment = ""
        if "form-user-value" in test_results:
            comment += "Performed by " + test_results.pop("form-user-value")
        else:
            del test_results["form-user-skipped"]
        # Set review status to approved if instance has already been checked
        if "form-approval-value" in test_results:
            comment += "\nReviewed by " + \
                test_results.pop("form-approval-value")
            # status (1: Unreviewed, 2: Approved 3 :Rejected)
            test_results["status"] = 2
        else:
            test_results["status"] = 1
            del test_results["form-approval-skipped"]
        if "form-comment-value" in test_results:
            comment += "\n" + test_results["form-comment-value"]
            del test_results["form-comment-value"]
        else:
            del test_results["form-comment-skipped"]
        comment += "\nRow " + str(data[0][1])
        test_results["comment"] = comment

        # Add the management form data
        num_fields = str(len(test_results) - 2)
        test_results.update({
            "work_started": date.strftime("%d-%m-%Y %H:%M"),
            "work_completed": (date + datetime.timedelta(
                minutes=30)).strftime("%d-%m-%Y %H:%M"),
            "form-TOTAL_FORMS": num_fields,
            "form-INITIAL_FORMS": num_fields,
            "form-MAX_NUM_FORMS": "1000"
        })

        logger.debug('Test Results (Full): %s', pprint.pformat(test_results))

        return test_results

    def submit_data(self, viewid=None, startdate=None, enddate=None,
                    patientid=None, utc=6, mapping=None, progressfunc=None,
                    updatefunc=None, dryrun=False):
        """Submit the test results to the QATrack+ server"""

        # Set a default mapping
        if mapping is None:
            mapping = {
                "19607": [0, "bool"],
                "19608": [1, "bool"],
                "20740": [2, "bool"],
                "19609": [3, "bool"],
                "19635": [4, "bool"],
                "19610": [5, "bool"],
                "19661": [6, "float"],
                "19663": [7, "float"],
                "19874": [8, "float"],
                "19875": [9, "float"],
                "19873": [10, "float"],
                "21396": [11, "bool"],
                "21395": [12, "bool"],
                "21690": [13, "bool"],
                "19613": [14, "bool"],
                "19626": [15, "bool"],
                "19627": [16, "bool"],
                "19628": [17, "bool"],
                "19639": ["user", "str"],
                "19640": ["approval", "str"],
                "20269": ["comment", "str"]
                }

        # Connect to the QATrack Server
        if progressfunc:
            progressfunc("Connecting to QATrack+ Server...")
        logger.info("Connecting to QATrack+ Server...")
        rs = resultssubmitter.ResultsSubmitter(
            self.qat_url, self.qat_username, self.qat_password)
        logger.debug("%s %s %s",
                     self.qat_url, self.qat_username, self.qat_password)

        # Connect to the MosaiQ DB Server
        if progressfunc:
            progressfunc("Connecting to MosaiQ database...")
        obsreqs = self.get_mosaiq_obsreq(viewid, startdate, enddate, patientid)
        logger.debug("Obsreqs: %s", obsreqs)
        logger.info("Number of rows: %d", len(obsreqs))
        if len(obsreqs):
            logger.info("Dates from: %s, %s",
                        obsreqs[0][1].strftime(dtformat),
                        obsreqs[-1][1].strftime(dtformat))
        else:
            nodatamsg = "No data to import from " + \
                str(startdate) + " to " + str(enddate) + "."
            if progressfunc:
                progressfunc(nodatamsg)
            logger.info(nodatamsg)
            return

        # Iterate over the selected rows
        start = 1
        end = len(obsreqs)
        rownum = start
        logger.info("Number of rows: %d", end)
        for obsreq in obsreqs:
            date = obsreq[1].strftime(dtformat)
            logger.info("Row # %s, Date: %s",
                        rownum, date)
            data = self.get_mosaiq_obsset(obsreq[0])
            logger.debug("Data: %s %d", data, len(data))
            try:
                test_results = self.convert_test_result(
                    data, mapping, obsreq[1])
            except:
                if updatefunc:
                    updatefunc(utc, date)
                raise Exception("Error with assessment from : " + date +
                                ". Please check data and retry.")
            # Update the progress function
            if progressfunc:
                progressfunc(
                    "Reading record: " + str(rownum) + " of " + str(end))
            # If the test results aren't None, submit to server
            if test_results and not dryrun:
                logger.info("Submitting Row # %s to server", rownum)
                text = rs.submit_data(utc, test_results)
                with open("result.html", 'w') as f:
                    f.write(text)
            rownum = rownum + 1
            # Update the update function after the result has been submitted
            dateplusone = (obsreq[1] + datetime.timedelta(days=1)).strftime(
                dtformat)
            if updatefunc:
                updatefunc(utc, dateplusone)

        completionmsg = "Imported " + str(rownum - 1) + " rows from " + \
            str(startdate) + " to " + dateplusone + "."
        if progressfunc:
            progressfunc(completionmsg)
        logger.info(completionmsg)

if __name__ == '__main__':

    import sys
    import argparse
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
        description="Read assessments from the MosaiQ DB " +
        "and submit them to QATrack+.")
    parser.add_argument("viewid",
                        help="ID of the assessment view",
                        type=int)
    parser.add_argument("server",
                        help="MosaiQ DB server")
    parser.add_argument("username",
                        help="MosaiQ DB username")
    parser.add_argument("password",
                        help="MosaiQ DB password")
    parser.add_argument("-p", "--patientid",
                        help="MosaiQ DB patient ID value (Pat_ID1)",
                        type=int)
    parser.add_argument("-u", "--utc",
                        help="QATrack+ UnitTestCollection id",
                        type=int)
    parser.add_argument("-sd", "--date",
                        help="Start date to sync MosaiQ tx records from")
    parser.add_argument("-ed", "--enddate",
                        help="End date to sync MosaiQ tx records from")
    parser.add_argument("-d", "--debug",
                        help="Show debug log",
                        action="store_true")
    parser.add_argument("-y", "--dryrun",
                        help="Dry run mode (read data without submitting)",
                        action="store_true")

    # If there are no arguments, display help and exit
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()

    # Set debug logging if the debug flag is set
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug(args)

    # Read and submit the MosaiQ Database Assessments
    reader = MQAssessmentsSubmitter(args.server, args.username, args.password)
    reader.submit_data(
        viewid=args.viewid, startdate=args.date, enddate=args.enddate,
        patientid=args.patientid, utc=args.utc, progressfunc=logger.debug,
        dryrun=args.dryrun)
