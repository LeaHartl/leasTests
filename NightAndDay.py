#! /usr/bin/env python3
# Query ACIS station data for lon and lat, compute sunrise times

# load standard modules
import argparse
import json
import urllib
import yaml
import os.path
import jinja2
import numpy as np
import pandas as pd
import ephem 
# from pandas import Series, DataFrame, Panel
import datetime
import pytz
# load ACRC modules
import data_helpers as dh
import stations as ws




## some helper functions

## turn time stamp into seconds
def get_sec(time_str):
    time_str = str(time_str.values)
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)

## make range string for highcharts
def makeRange(xData, lowdata, highdata):
    lowdata = lowdata.tolist()
    highdata = highdata.tolist()
    current = '['
    for index, value in enumerate(highdata):
        temp = '['
        temp += str(xData[index]) + ',' 

        #conditional 
        # if lowdata[index] < value :
        temp += str(lowdata[index]) + ',' 
        temp += str(value) + ']'
        current += temp + ','
        # if lowdata[index] >= value :
            # temp += str(value) + ',' 
            # temp += str(lowdata[index]) + ']'
            # current += temp + ','

    current = current[:-1]
    current += ']'
    current = current.replace("nan", "null")
    return current

## customize ephem library output
def rise_set(horizon, center, station, lat, lon, dates ):
    #ephem library thinks in UTC!
    station.pressure = 0
    station.horizon = horizon
    station.lat = str(lat)
    station.lon = str(lon) 
    rises_out = []
    sets_out = []
    dates = dates.dt.strftime('%Y/%m/%d %H:%M')

    for ix,row in dates.items():
        station.date = dates[ix]
        try:
            rises = station.next_rising(ephem.Sun(), use_center=center)
            sets = station.next_setting(ephem.Sun(), use_center=center)

            rises_out.append(str(rises))
            sets_out.append(str(sets))
        #output nan if arctic night or arctic day error ocurrs
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            rises_out.append('NaN')
            sets_out.append('NaN')

    rises_out = pd.DataFrame({'rise': rises_out})    
    sets_out = pd.DataFrame({'set': sets_out})   

    #return times in akst, i.e. utc - 9 hours
    return (pd.to_datetime(rises_out['rise'], format = '%Y/%m/%d %H:%M:%S') - pd.Timedelta(hours=9) , pd.to_datetime(sets_out['set'], format = '%Y/%m/%d %H:%M:%S') - pd.Timedelta(hours=9) )



# load hichcharts template
PATH = os.path.dirname(os.path.abspath(__file__))
templateLoader = jinja2.FileSystemLoader( searchpath=PATH )
templateEnv = jinja2.Environment( loader=templateLoader )
TEMPLATE_ENVIRONMENT = jinja2.Environment(
    autoescape=False,
    loader=jinja2.FileSystemLoader(os.path.join(PATH)),
    trim_blocks=False)

template = templateEnv.get_template('daylight.html')
# parse command line
parser = argparse.ArgumentParser()
parser.add_argument("type", help="station type ([1-4]")
parser.add_argument("dir", help="name of output directory")
args = parser.parse_args()

# set output directory
output_dir = args.dir
if not os.path.exists(output_dir):
  os.makedirs(output_dir)




## MAIN ##
# #####################################
#Set ACIS variables
acis_daily_all = {
  "elems": [{"name":"avgt", "interval":"dly", "duration":"dly", "reduce":"mean"}]
}
acis_station_url = "https://data.rcc-acis.org/StnData?"
# ####################################

# setup data dict
anno_data = {}
anno_data["station"] = []
anno_data["lat"] = []
anno_data["lon"] = []

station_ll = {}
times = {}

#horizon angle day (this overrides ephem settings for computing atmospheric refraction near horizon and sets these parameters to match the Navy Astronomical Almanac, see http://rhodesmill.org/pyephem/rise-set.html#computing-twilight)
horizonDay = '-0:34'
#twilight horizon angle
horizonCivil = '-6'
horizonNautical = '-12'
horizonAstronomical = '-18'
place = []


#get location data from acis
for key, value in ws.stations.items():
    if value[int(args.type)] == 1: #use first order stations

        acis_params = {}
        acis_params['sdate'] = '2017-01-01' #dummy dates
        acis_params['edate'] = '2017-01-05'
        acis_params['sid'] = value[0]

        acis_params.update(acis_daily_all) #dummy elem, just extract position and name.
        request_params = urllib.parse.urlencode({'params': json.dumps(acis_params)})

        acis_station_data = dh.read_data(acis_station_url, params=request_params)

        # # process data into dictionary
        station_ll = acis_station_data['meta']['ll']
        lon, lat = station_ll

        anno_data['station'].append(key)
        anno_data['lat'].append(lat)
        anno_data['lon'].append(lon)

        meta_df = pd.DataFrame(anno_data, columns=['station', 'lat', 'lon'])
        meta_df[['lat', 'lon']] =  meta_df[['lat', 'lon']].astype(float) # convert to float

        times[key] = pd.DataFrame(columns=['dates'])
        times[key]['dates'] = pd.date_range(start= '2018-01-01 00:00', end = '2018-12-31 00:00')

## begin setup of variables to pass to highcharts 

string_date = {}
string_day = {}
string_civilAM = {}
string_civilPM = {}
string_nautAM = {}
string_nautPM = {}
string_astrAM = {}
string_astrPM = {}
string_nightAM = {}
string_nightPM = {}

seconds = {}

#generate times
for key, value in times.items():
    station = key
    station = ephem.Observer()

    print(key)
    times[key]['sunrise'], times[key]['sunset'] = rise_set(horizonDay, False, station, meta_df.loc[meta_df['station'] == key, 'lat'].item(), meta_df.loc[meta_df['station'] == key, 'lon'].item(), times[key]['dates'])
    times[key]['civil_rise'], times[key]['civil_set'] = rise_set(horizonCivil, True, station, meta_df.loc[meta_df['station'] == key, 'lat'].item(), meta_df.loc[meta_df['station'] == key, 'lon'].item(), times[key]['dates'])
    times[key]['naut_rise'], times[key]['naut_set'] = rise_set(horizonNautical, True, station, meta_df.loc[meta_df['station'] == key, 'lat'].item(), meta_df.loc[meta_df['station'] == key, 'lon'].item(), times[key]['dates'])
    times[key]['astr_rise'], times[key]['astr_set'] = rise_set(horizonAstronomical, True, station, meta_df.loc[meta_df['station'] == key, 'lat'].item(), meta_df.loc[meta_df['station'] == key, 'lon'].item(), times[key]['dates'])
    
    times[key]['dates']  =  pd.to_datetime(times[key]['dates']) 

    seconds[key] = pd.DataFrame(columns = times[key].columns)

    #convert time values to number of milliseconds in day (this is what highcharts wants)
    for column in times[key].columns:

        seconds[key][column] = times[key][column].dt.hour * 3600 + times[key][column].dt.minute * 60 + times[key][column].dt.second
        seconds[key][column] = seconds[key][column] * 1000

        #this adds a day if sunset is before noon
        seconds[key].loc[seconds[key]['civil_set'] < 12 * 3600 * 1000, 'civil_set'] = seconds[key]['civil_set'] + 24*3600*1000
        seconds[key].loc[seconds[key]['naut_set'] < 12 * 3600 * 1000, 'naut_set'] = seconds[key]['naut_set'] + 24*3600*1000
        seconds[key].loc[seconds[key]['astr_set'] < 12 * 3600 * 1000, 'astr_set'] = seconds[key]['astr_set'] + 24*3600*1000
        seconds[key].loc[seconds[key]['sunset'] < 12 * 3600 * 1000, 'sunset'] = seconds[key]['sunset'] + 24*3600*1000

    #day of year in millisecons for x axis
    seconds[key]['num'] = (seconds[key].index + 1) * 24 * 3600 *1000



## various attempts to fiddle with settings to fix the gaps
    AM = seconds[key]['astr_rise'].min()
    PM = seconds[key]['astr_set'].max()

    seconds[key]['zeroAM'] = 0
    seconds[key]['zeroPM'] = (24 * 3600 *1000) -1
    # seconds[key]['zeroAM'] = AM
    # seconds[key]['zeroPM'] = PM

    # seconds[key]['sunrise'].fillna(AM, inplace=True)
    # seconds[key]['sunset'].fillna(PM, inplace=True)

    # seconds[key]['civil_rise'].fillna(AM, inplace=True)
    # seconds[key]['civil_set'].fillna(PM, inplace=True)

    # seconds[key]['naut_rise'].fillna(AM, inplace=True)
    # seconds[key]['naut_set'].fillna(PM, inplace=True)

    # seconds[key]['astr_rise'].fillna(AM, inplace=True)
    # seconds[key]['astr_set'].fillna(PM, inplace=True)

    # seconds[key]['sunrise'].fillna(AM, inplace=True)
    # seconds[key]['sunset'].fillna(PM, inplace=True)


    # seconds[key].loc[seconds[key]['sunrise'] == np.nan, 'sunrise'] = 0
    # seconds[key].loc[seconds[key]['sunrise'] == np.nan, 'sunset'] = (24 * 3600 *1000) -1
    # print (seconds[key])
    # seconds[key]['civilAM2'] = seconds[key]['sunrise']
    # seconds[key].loc[seconds[key]['civilAM2']  seconds[key]['sunrise']

##

    # make strings to pass to highcharts. format: [xData, yData low end of range, yData high end of range]
    string_day[key] = makeRange(seconds[key]['num'], seconds[key]['sunrise'], seconds[key]['sunset'])
    string_civilAM[key] = makeRange(seconds[key]['num'], seconds[key]['civil_rise'], seconds[key]['sunrise'])
    string_civilPM[key] = makeRange(seconds[key]['num'], seconds[key]['sunset'], seconds[key]['civil_set'])
    string_nautAM[key] = makeRange(seconds[key]['num'], seconds[key]['naut_rise'], seconds[key]['civil_rise'])
    string_nautPM[key] = makeRange(seconds[key]['num'], seconds[key]['civil_set'], seconds[key]['naut_set'])
    string_astrAM[key] = makeRange(seconds[key]['num'], seconds[key]['astr_rise'], seconds[key]['naut_rise'])
    string_astrPM[key] = makeRange(seconds[key]['num'], seconds[key]['naut_set'], seconds[key]['astr_set'])
    string_nightAM[key] = makeRange(seconds[key]['num'], seconds[key]['zeroAM'], seconds[key]['astr_rise'])
    string_nightPM[key] = makeRange(seconds[key]['num'], seconds[key]['astr_set'], seconds[key]['zeroPM'])

#build variable to give to highcharts
    template_vars = {}
    name = []
    for i, key in enumerate(string_day):
        name = key
        if key == 'Cold Bay':
            name = 'ColdBay'
        if key == 'Delta Junction':
            name = 'DeltaJunction'
        if key == 'King Salmon':
            name = 'KingSalmon'
        if key == 'St. Paul Island':
            name = 'StPaulIsland'
        # print (name)    
        # else:    
        template_vars[name + 'Day'] = string_day[key]
        template_vars[name + 'Civil_twilight_AM'] = string_civilAM[key]
        template_vars[name + 'Civil_twilight_PM'] = string_civilPM[key]
        template_vars[name + 'Nautical_twilight_AM'] = string_nautAM[key]
        template_vars[name + 'Nautical_twilight_PM'] = string_nautPM[key]
        template_vars[name + 'Astro_twilight_AM'] = string_astrAM[key]
        template_vars[name + 'Astro_twilight_PM'] = string_astrPM[key]
        template_vars[name + 'Night_AM'] = string_nightAM[key]
        template_vars[name + 'Night_PM'] = string_nightPM[key]

    #pass to highcharts template
    output_file = output_dir + "/daynight.html"
    handle = open(output_file, 'w')
    handle.write(template.render(template_vars))
    handle.close()


