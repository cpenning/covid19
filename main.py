#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr  1 21:17:34 2020

@author: cpenning@milo.org
@description: Messing with the covid-19 data from the eu cdc
"""

import os
import requests
import sys

import matplotlib.pyplot as plt
import pandas as pd

from datetime import date

# Clean up your plots!
plt.close('all')

# The full monty for all rows displayed
pd.set_option('display.max_columns', None)

# Whence the data?
https_template='https://{}/{}/{}'

ecdc_host='www.ecdc.europa.eu'
ecdc_datapath='sites/default/files/documents'
ecdc_fntemplate='COVID-19-geographic-disbtribution-worldwide-{}.xlsx'

# Store it thither, in case we need it again
datafile_template = '{}/data/{}'

def get_filename(fn):
    """
    Yeah, I'm gonna need you to check the cache for that file.
      If it's not there, I'm gonna need you to go get it.
    """
    cache_fn=datafile_template.format(os.getcwd(),fn)
    # TODO: Check that this file is non-empty
    if not os.path.exists(cache_fn):
        remote_fn=https_template.format(ecdc_host,ecdc_datapath,fn)
        print("Downloading {} ...".format(remote_fn))
        r = requests.get(remote_fn, allow_redirects=True)
        if r.status_code != 200: # Game over, man. Game over.
            print(r)
            sys.exit()
        with open(cache_fn,'wb') as ofh:
            ofh.write(r.content)
    return cache_fn

if __name__ == '__main__':
    # Read today's news
    dateRep = str(date.today())
    #dateRep = '2020-04-01'
    ecdc_fn=ecdc_fntemplate.format(dateRep)
    df = pd.read_excel(get_filename(ecdc_fn))
    df = df.drop(['geoId', 'countriesAndTerritories', 'day', 'month', 'year'], axis=1)
    df = df.sort_values(by=['countryterritoryCode', 'dateRep'])
    df['Date'] = pd.to_datetime(df['dateRep'])
    df['deaths_cumulative'] = df.groupby([df.countryterritoryCode])['deaths'].apply(lambda x: x.cumsum())
    df['cases_cumulative'] = df.groupby([df.countryterritoryCode])['cases'].apply(lambda x: x.cumsum())
    df['dc'] = df['deaths_cumulative']/df['cases_cumulative']
    df['dp'] = df['deaths_cumulative']/(df['popData2018']/100000.0)
    country_groups = df.groupby(df.countryterritoryCode)

    rok = country_groups.get_group("KOR")
    kdc = rok['dc'].to_numpy() # Korea deaths/case
    kdp = rok['dp'].to_numpy() # Korea deaths/100k of population

    plt.figure()
    #countries = ['USA', 'ESP', 'KOR']
    countries = [ 'ITA' ]
    for country in countries:
        c = country_groups.get_group(country).copy().set_index('Date')
        print(c)
        c['deltaKC'] = c['cases_cumulative']*(c['dc'] - kdc)
        c['deltaKP'] = c['deaths_cumulative']*(c['dp'] - kdp)/c['dp']
        c['deltaKC'].plot()
        c['deltaKP'].plot()