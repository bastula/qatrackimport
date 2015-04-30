# qatrackimport

This package consists of several helper scripts and a GUI that allow easy import of radiotherapy machine quality assurance (QA) data into [QATrack+](http://qatrackplus.com).

#### Screenshot:

![Screenshot of GUI](https://cloud.githubusercontent.com/assets/61406/7419859/7a9827f8-ef3d-11e4-9c6f-88e0242a9411.png)

Current import sources are:

* *Microsoft Excel files* (used for importing CT Daily QA stored in .xlsx format)
* *Elekta MosaiQ* (used to read QA stored in a patient assessment)


The code runs on Python 2/3 and requires the following modules:

* [openpyxl](https://bitbucket.org/openpyxl/openpyxl) - used to read Excel 2007/2010 xlsx files
* [pymssql](http://www.pymssql.org/) - used to read from the MosaiQ database
* [PyQt](http://www.riverbankcomputing.com/software/pyqt/) (optional) - used to dislplay the GUI (PyQt4 and PyQt5 both work)

All script configuration options are documented by running the command with the argument ```--help```

To automate import, use the GUI and create a corresponding ```config.json``` file. A sample one is as follows:

```json
{
   "machines":[
      {
         "id":"1",
         "name":"Proton CT Simulator Daily",
         "type":"ct_daily_excel",
         "file":"CT_Daily_QA.xlsx"
      },
      {
         "id":"16",
         "name":"GTR4 Daily",
         "type":"mosaiq_assessment",
         "viewid": 19604,
         "patientid": 10249,
         "mapping": {
            "19607": [0, "bool"],
            "19608": [1, "bool"],
            "20740": [2, "bool"],
            "19609": [3, "bool"],
            "19639": ["user", "str"],
            "19640": ["approval", "str"],
            "20269": ["comment", "str"]
         }
      }
   ],
   "qatrack_credentials":{
      "url":"http://127.0.0.1/",
      "username":"admin",
      "password":"admin"
   },
   "mosaiq_credentials":{
      "server":"mosaiqdb",
      "username":"dbuser",
      "password":"dbpassword"
   }
}

```
