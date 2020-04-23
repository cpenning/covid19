#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr  1 21:17:34 2020

@author: cpenning@milo.org
@description: Messing with the covid-19 data from the eu cdc
"""

import locale
import os
import requests
import sys

import matplotlib.pyplot as plt
import pandas as pd

from collections import OrderedDict
from datetime import date, time, datetime, timedelta

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
          'Date' : ('Comp. Date', lambda x: x.date()),
          'cases_cumulative': ('Cases', lambda x: int(x+0.5)),
          'deaths_cumulative': ('Deaths', lambda x: int(x+0.5)),
          'deltaCC': ('ΔComp (C)', lambda x: int(x+0.5)),
          'deltaCP': ('ΔComp (P)', lambda x: int(x+0.5))})

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

def main(compisocc='KOR',today=date.today()):
    # Read today's news
    dateRep = str(today)
    ecdc_fn=ecdc_fntemplate.format(dateRep)
    df = pd.read_excel(get_filename(ecdc_fn))
    print(df.keys())

    # Clean up a little
    df['dateRep'] = [str(date(year,month,day)) for day, month, year in zip(df['day'], df['month'], df['year'])]
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

    # Get Comparison Numbers
    comp = country_groups.get_group(compisocc)

    compday0 = first_cases[compisocc]

    # Keep track of where in the comparison timeline a country is
    compdict=dict()
    countryday = dict()

    compdays = today - compday0

    countries = ['AUS', 'TWN', 'KOR', 'DEU', 'USA', 'IRN', 'ESP', 'ITA']
    #countries = ['USA', 'KOR', 'SWE', 'NOR']
    cdata = OrderedDict()

    dttoday = datetime.combine(today, time.min)
    for country in countries:
        cdays = today-first_cases[country]
        if compdays >= cdays:
            # Comparison country has had the infection as long or longer
            #   than this country. Look at where the comparison country was
            #   relative to this country
            cday = compday0 + cdays
            compdict[country] = comp[comp['Date'] ==  datetime.combine(cday, time.min)].to_dict()
            countryday[country] = dttoday
        else:
            # Comparison country has not had the infection as long as this
            #   country. Look at where this country was relative to the
            #   comparison country
            cday = dttoday - (compday0 - first_cases[country])
            compdict[country] = comp[comp['Date'] == dttoday].to_dict()
            countryday[country] = cday

        c = country_groups.get_group(country).copy()

        # Get the relative point in time where we are for the comparison
        cdc = compdict[country]['dc'][list(compdict[country]['dc'])[0]]
        cdp = compdict[country]['dp'][list(compdict[country]['dp'])[0]]

        # HERE! Here is the comparison code.
        c['deltaCC'] = c['cases_cumulative']*(c['dc'] - cdc)
        c['deltaCP'] = c['deaths_cumulative']*(c['dp'] - cdp)/c['dp']

        # Get data for this country
        cdata[country] = c[c['Date'] == countryday[country]].to_dict()

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
    
    vtable = list()
    
    for row in ctable.values:
        vrow = list()
        for cell in row:
            if isinstance(cell, int):
                #vstr = locale.format_string("%d", cell, grouping=True)
                vstr = "{:,}".format(cell)
                vrow.append(vstr)
            else:
                vrow.append(cell)
        vtable.append(vrow)

    # Display the table
    fig, ax = plt.subplots()

    # hide axes
    fig.patch.set_visible(False)
    sttemplate = 'Comparison of COVID-19 fatalities relative to {}'
    plt.title(sttemplate.format(compisocc),pad=0)
    ax.axis('off')
    ax.axis('tight')
    t = ax.table(cellText=vtable, colLabels=ctable.columns, loc='center')
    t.auto_set_font_size(False)
    t.set_fontsize(8)
    fig.tight_layout()
    plt.show()

if __name__ == '__main__':
    # TODO: Maybe add command line arguments
    #main('KOR',date.today() - timedelta(days = 1))
    main()