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

from collections import OrderedDict
from datetime import date, time, datetime

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

# Map from ecdc field names to display field names and display value
#   conversion functions. Used in the map_fields function below.
fnmap = OrderedDict({
          'countryterritoryCode': ('Country', lambda x: x),
          'popData2018': ('Pop (2018)', lambda x: int(x+0.5)),
          'Date' : ('Date', lambda x: x.date()),
          'cases_cumulative': ('Cases', lambda x: int(x+0.5)),
          'deaths_cumulative': ('Deaths', lambda x: int(x+0.5)),
          'deltaKC': ('ΔKOR (C)', lambda x: int(x+0.5)),
          'deltaKP': ('ΔKOR (P)', lambda x: int(x+0.5))})

def map_fields(d):
    """
    Map the fields to readable names, and format the values
    """
    rval = OrderedDict()
    for fn in fnmap:
        rval[fnmap[fn][0]] = fnmap[fn][1](d[fn])
    return rval

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
    today = date.today()
    dateRep = str(today)
    ecdc_fn=ecdc_fntemplate.format(dateRep)
    df = pd.read_excel(get_filename(ecdc_fn))

    # Clean up a little
    df = df.drop(['geoId', 'countriesAndTerritories', 'day', 'month', 'year'], axis=1)
    df = df.sort_values(by=['countryterritoryCode', 'dateRep'])

    # For date computations
    df['Date'] = pd.to_datetime(df['dateRep'])
    
    # Calculate cumulative values
    df['deaths_cumulative'] = df.groupby([df.countryterritoryCode])['deaths'].apply(lambda x: x.cumsum())
    df['cases_cumulative'] = df.groupby([df.countryterritoryCode])['cases'].apply(lambda x: x.cumsum())

    # Calculate Deaths/Case and Deaths/Population
    df['dc'] = df['deaths_cumulative']/df['cases_cumulative']
    df['dp'] = df['deaths_cumulative']/(df['popData2018']/100000.0)

    # Group be country
    country_groups = df.groupby(df.countryterritoryCode)

    # When was the first reported covid19 case in a country?
    first_cases = dict()

    for country, country_data in country_groups:
        idx = country_data.cases_cumulative.ne(0).idxmax()
        first_cases[country] = country_data.loc[idx]['Date'].date()

    # Get Korea's Numbers
    rok = country_groups.get_group("KOR")   

    korday0 = first_cases['KOR']

    # Keep track of where in Korea's timeline a country is
    # XXX: will break things for any country that had a case before KOR
    kor=dict()
    kordays = today - korday0
    
    for k in first_cases:
        cdays = today-first_cases[k]
        kday = korday0 + cdays
        kor[k] = rok[rok['Date'] ==  datetime.combine(kday, time.min)].to_dict()

    # Now we get to our comparisons.
    # TODO: Figure out an ordering that makes sense
    countries = ['AUS', 'TWN', 'KOR', 'DEU', 'USA', 'IRN', 'ESP', 'ITA']

    cdata = OrderedDict()


    for country in countries:
        c = country_groups.get_group(country).copy()
        
        # Get the relative point in time where we are for KOR
        kdc = kor[country]['dc'][list(kor[country]['dc'])[0]]
        kdp = kor[country]['dp'][list(kor[country]['dp'])[0]]

        # HERE! Here is the comparison code.
        c['deltaKC'] = c['cases_cumulative']*(c['dc'] - kdc)
        c['deltaKP'] = c['deaths_cumulative']*(c['dp'] - kdp)/c['dp']

        # Get today's data for this country
        cdata[country] = c[c['dateRep'] == dateRep].to_dict()

        # Good God, there's got to be a better way
        for k in cdata[country]:
            v = cdata[country][k]
            k0 = list(v.keys())[0]
            v = v[k0]
            cdata[country][k] = v

        # Prep data for display
        cdata[country] = map_fields(cdata[country])
        cdata[country]['days'] = (today-first_cases[country]).days

    ctable = pd.DataFrame(cdata).T
    print(ctable)

    # Display the table
    columns = tuple(countries)
    fig, ax = plt.subplots()

    # hide axes
    fig.patch.set_visible(False)
    ax.axis('off')
    ax.axis('tight')
    t = ax.table(cellText=ctable.values, colLabels=ctable.columns, loc='center')
    t.auto_set_font_size(False)
    t.set_fontsize(8)
    fig.tight_layout()
    plt.show()