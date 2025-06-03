# Canadian Basic Amateur Radio Certificate Study Tool

#### 2025-05-26
#### Version 0.1
#### Jonathan Stern - jonathan@sternman.net

 `DISCLAIMER: This code comes with no warranties and is as-is. 
 It was written by Claude Sonnet 3.5 in VS Code using Github Copilot.
 It works, it likely has errors`

This runs streamlit and is a web based study tool for Canadian Basic Amateur Radio Certificate.
You can take sample tests using exam questions and it will save results based on the email of the user taking it.
You can review your historical results and learn which areas you need to focus on to get that passing grade (with honours).

## Overview

Uses questions and answers found [here](https://apc-cap.ic.gc.ca/datafiles/amat_basic_quest.zip). (This will download a zip file).

Inside the zip is a flat file called amat_basic_quest_delim.txt

The data in this file are semi-colon delimited. So pasting into excel will put it into just one column, but you can use the text-to-column feature on the ; character to make this human readable.

I removed the french answers.

I added three columns to the left of the question Id and called them **Section**, **Group** and **Question**. Then I split the question Id - (but only the last two) to populate the three fields.

I added in a correct answer tab as well, but that was for my initial studying - and not necessary in python.

The "database" for this app is ham.xlsx. Python will read the contents into a pandas dataframe and from there the data can be manipulated further.

Streamlit is used as the web wrapper. Also provides an easy way to make forms and visualizations for capturing and representing the captured data.

UPDATE:

I have modified the files to save to Azure blob storage as the streamlit deployment would overwrite or delete saved work. The share.streamlit.io hosting platform is limited in its deployment options. While an Azure blob storage account incurs costs, it will be extremely small for a project like this. < $10/year

Set a normal non ADLS gen 2 account, copy key 1 or 2 connection string and set that in your local `.env` file.

```AZURE_STORAGE_CONNECTION_STRING=paste your connection string here```

## Usage:

>Likely requires python 3.8 or later, written on python 3.10.8

Setup a python environment

```python -m venv .venv```

Install the requirements file

```pip install -r requirements.txt```

This will install all necessary packages to make this run.

To launch the app

```streamlit run test.py```

***

App is also deployed to [streamlit](https://amateurradiostudy.streamlit.app/)

__https://amateurradiostudy.streamlit.app/__

The app will be deployed on commit to the master branch.

The repo needs to be fixed to accommodate more contributers.


> No license is available



