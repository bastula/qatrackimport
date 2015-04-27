#!/usr/bin/env python
# -*- coding: utf-8 -*-
# qatrackimportgui.py
"""Main file for qatrackimportgui."""
# Copyright (c) 2015 Aditya Panchal


# Configure logging for qatrackimportgui
import logging
import logging.handlers
import traceback
import pprint
logger = logging.getLogger('qatrackimport.gui')

try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, qApp, QMessageBox,
                                 QListWidgetItem)
    from PyQt5 import uic
    from PyQt5.QtCore import Qt
except:
    from PyQt4.QtGui import (QApplication, QMainWindow, qApp, QMessageBox,
                             QListWidgetItem)
    from PyQt4 import uic
    from PyQt4.QtCore import Qt
import json
import threading
import ctdailyqasubmitter
import mqassessmentssubmitter


class QATrackImportGui(QMainWindow):

    def __init__(self, debug=False):
        super(QATrackImportGui, self).__init__()

        self.initLogging(debug)

        # Load the ui from the Qt Designer file
        self.ui = uic.loadUi('resources/main.ui')
        self.ui.show()
        self.createActions()

        self.initSettings()
        self.populateMachines()

    def initLogging(self, debug=False):
        """Initialize the logging system."""

        # Initialize logging
        logger = logging.getLogger('qatrackimport')
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(ch)

        # Add file logger
        fhlog = 'qatrackimport.log'
        fh = logging.handlers.RotatingFileHandler(
            fhlog, maxBytes=524288, backupCount=7)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

        # Configure the exception hook to process threads as well
        # self.InstallThreadExcepthook()

        # Remap the exception hook so that we can log and display exceptions
        def LogExcepthook(*exc_info):
            # Log the exception
            text = "".join(traceback.format_exception(*exc_info))
            logger.error("Unhandled exception: %s", text)
            QMessageBox.critical(self, "Exception", text)

        sys.excepthook = LogExcepthook

    def createActions(self):
        """Set up the actions used in the application."""
        self.ui.action_Exit.triggered.connect(qApp.quit)
        self.ui.action_About.triggered.connect(self.about)
        self.ui.btnSubmit.clicked.connect(self.submitData)
        self.ui.action_Dryrun_Mode.toggled.connect(self.enableDryRun)

    def enableDryRun(self, dryrun):
        "Display the status of Dry run Mode."

        msg = "Dry run is "
        msg += "enabled" if dryrun else "disabled"
        logger.info(msg)
        self.ui.statusbar.showMessage(msg)

    def initSettings(self):
        """Initialize the settings for the QATrack+ Import Gui."""

        # Set up the configuration
        configfile = 'config.json'
        try:
            with open(configfile) as c:
                self.config = json.load(c)
        except:
            QMessageBox.information(self, "Invalid configuration file",
                                    "Set config.json before running.")
            self.config = {"machines": []}

        # Set up the progress file
        self.progressfile = 'progress.json'
        try:
            with open(self.progressfile) as p:
                self.progress = json.load(p)
        except:
            self.progress = {}

        logger.info('Machine progress: %s', pprint.pformat(self.progress))

    def about(self):
        """Display an about screen for the application."""
        QMessageBox.about(self, "About QATrack+ Importer",
                          "<b>QATrack+ Importer</b> allows users to import "
                          "existing data from various sources to QATrack+."
                          "<p>For more information visit: "
                          "<a href=http://github.com/bastula/qatrackimport>"
                          "http://github.com/bastula/qatrackimport</a>")

    def populateMachines(self):
        """Load the machine data into QATrack+ Import."""

        self.ui.listMachines.clear()
        for m in self.config['machines']:
            item = QListWidgetItem(m['name'])
            item.setData(Qt.UserRole, m['id'])
            self.ui.listMachines.addItem(item)

    def submitData(self):
        """Submit the machine data to the QATrack+ server."""

        qatcreds = self.config['qatrack_credentials']

        # Determine which machines are selected
        for i in self.ui.listMachines.selectedItems():
            machineid = i.data(Qt.UserRole)
            for m in self.config['machines']:
                # Find the machine from config
                if m['id'] == machineid:
                    # Submit data for CT Daily Excel
                    if m['type'] == "ct_daily_excel":
                        logger.info("Submitting data for: %s", m["name"])
                        reader = ctdailyqasubmitter.CTDailyQASubmitter(
                            m["file"])
                        reader.read_excel_file()
                        reader.set_qatrack_server(
                            url=qatcreds['url'],
                            username=qatcreds['username'],
                            password=qatcreds['password'])
                        reader.submit_data(
                            utc=1, startrow=self.progress[m['id']],
                            progressfunc=self.ui.statusbar.showMessage,
                            updatefunc=self.saveProgress,
                            dryrun=self.ui.action_Dryrun_Mode.isChecked())
                    # Submit data for MosaiQ Assessment
                    elif m['type'] == "mosaiq_assessment":
                        logger.info("Submitting data for: %s", m["name"])
                        mqcreds = self.config['mosaiq_credentials']
                        reader = mqassessmentssubmitter.MQAssessmentsSubmitter(
                            server=mqcreds['server'],
                            username=mqcreds['username'],
                            password=mqcreds['password'])
                        reader.set_qatrack_server(
                            url=qatcreds['url'],
                            username=qatcreds['username'],
                            password=qatcreds['password'])
                        reader.submit_data(
                            viewid=m['viewid'],
                            startdate=self.getProgress(m['id']),
                            patientid=m['patientid'], utc=m['id'],
                            mapping=byteify(m['mapping']),
                            progressfunc=self.ui.statusbar.showMessage,
                            updatefunc=self.saveProgress,
                            dryrun=self.ui.action_Dryrun_Mode.isChecked())
                    break

    def saveProgress(self, utc, progress):
        """Save the progress of the import operation to disk."""

        self.progress[str(utc)] = progress
        # Only write out the file if not in Dry run mode
        if not self.ui.action_Dryrun_Mode.isChecked():
            with open(self.progressfile, 'w') as p:
                json.dump(self.progress, p)

    def getProgress(self, utc):
        """Get the current progress of the import operation."""

        return self.progress[utc] if utc in self.progress else None


# ############################## Other Functions ##############################

    def InstallThreadExcepthook(self):
        """Workaround for sys.excepthook thread bug from Jonathan Ellis
            (http://bugs.python.org/issue1230540).
            Call once from __main__ before creating any threads.
            If using psyco, call psyco.cannotcompile(threading.Thread.run)
            since this replaces a new-style class method."""

        run_old = threading.Thread.run

        def Run(*args, **kwargs):
            try:
                run_old(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                sys.excepthook(*sys.exc_info())
        threading.Thread.run = Run


def byteify(input):
    """Convert decoded json from unicode to byte strings (Python 2.x).
       Taken from: http://stackoverflow.com/a/13105359/74123."""

    import sys

    # Skip if on Python 3 or higher as it deals with unicode natively
    if sys.version_info[0] >= 3:
        return input
    elif isinstance(input, dict):
        return {byteify(key): byteify(value)
                for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input


if __name__ == '__main__':

    import sys
    import argparse

    # Set up argparser to parse the command-line arguments
    class DefaultParser(argparse.ArgumentParser):
        def error(self, message):
            sys.stderr.write('error: %s\n' % message)
            self.print_help()
            sys.exit(2)

    parser = DefaultParser(
        description="GUI to submit test results to a QATrack+ server.")
    parser.add_argument("-d", "--debug",
                        help="Show debug log",
                        action="store_true")

    args = parser.parse_args()

    app = QApplication(sys.argv)
    mainWindow = QATrackImportGui(args.debug)
    sys.exit(app.exec_())
