#! /usr/bin/env python3
# Query ACIS station data for lon and lat, compute sunrise times
# Fill HighChartes template

# load standard modules
import argparse
import json
import urllib
import os
import jinja2
import pandas as pd
import ephem 
import datetime as dt
import logging
# import pytz <-- we should probably use this instead of hardcoding timezone offset 
# load ACRC modules
import data_helpers as dh
import stations as ws

logging.basicConfig(level=logging.DEBUG)

## configuration
TEMPLATEFN = 'daylight.html'
OUTPUTFN = 'daynight.html'
PATH = os.path.dirname(os.path.abspath(__file__))

# ACIS variables
ACIS_STATION_URL = "https://data.rcc-acis.org/StnMeta?"

TIMEZONEOFFSET_H = -9

# ephem variables
# horizon angle day (this overrides ephem settings for computing atmospheric refraction 
# near horizon and sets these parameters to match the Navy Astronomical Almanac
# see http://rhodesmill.org/pyephem/rise-set.html#computing-twilight)
horizonDay = '-0:34'
#twilight horizon angles
horizonCivil = '-6'
horizonNautical = '-12'
horizonAstronomical = '-18'

def load_template(path=PATH, templatefn=TEMPLATEFN):
    """Load jinja2 template"""
    templateLoader = jinja2.FileSystemLoader( searchpath=PATH )
    templateEnv = jinja2.Environment( loader=templateLoader )
    return templateEnv.get_template(TEMPLATEFN)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "type", help="station type ([1-4]",
        default=1)
    parser.add_argument(
        "dir", help="name of output directory",
        default='testdir')
    return parser.parse_args()


def get_acis_stn_latlon(
        acis_station_url=ACIS_STATION_URL,
        stationtype=1):
    stations = [
        (key, val[0]) for (key, val) in ws.stations.items() 
            if val[stationtype] == 1]
    stationnamess = [item[0] for item in stations]
    stationIDs = [item[1] for item in stations]
    #get location data from acis
    logging.info("Getting latlon data for stations")
    acis_params = {}
    acis_params['sids'] = ','.join(stationIDs)
    acis_params['meta'] = 'll'
    acis_station_data = dh.read_data(acis_station_url, params=acis_params)
    station_meta = { 
        name: {'lon': item['ll'][0], 'lat': item['ll'][1]} 
        for (name, item) in zip(stationnamess, acis_station_data['meta'])
    }
    return station_meta


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
    current = current[:-1]
    current += ']'
    current = current.replace("nan", "null")
    return current

# check if a date is in winter
def iswinter(somedatetime):
    theyear = somedatetime.year
    return (
        somedatetime < dt.datetime(theyear, 3, 21) or
        somedatetime > dt.datetime(theyear, 10, 21)
        )


## customize ephem library output
def rise_set(horizon, center, station, lat, lon, dates ):
    #ephem library thinks in UTC!
    station.pressure = 0
    station.horizon = horizon
    station.lat = str(lat)
    station.lon = str(lon) 
    rises_out = []
    sets_out = []
    dates = dates - pd.Timedelta(hours=TIMEZONEOFFSET_H)
    dates = dates.dt.strftime('%Y/%m/%d %H:%M')

    for ix, row in dates.items():
        station.date = dates[ix]
        try:
            rises = station.next_rising(ephem.Sun(), use_center=center)
            sets = station.next_setting(ephem.Sun(), use_center=center)

            rises_out.append(str(rises))
            sets_out.append(str(sets))
        #output nan if arctic night or arctic day error ocurrs
        except ephem.CircumpolarError :
            thedate_dt = dt.datetime.strptime(dates[ix], '%Y/%m/%d %H:%M') 
            if iswinter(thedate_dt):
                rises_out.append((dt.datetime.strptime(dates[ix], '%Y/%m/%d %H:%M') + dt.timedelta(hours=12)).strftime('%Y/%m/%d %H:%M'))
                sets_out.append((dt.datetime.strptime(dates[ix], '%Y/%m/%d %H:%M') + dt.timedelta(hours=12)).strftime('%Y/%m/%d %H:%M'))
            else: 
                rises_out.append(dates[ix])
                sets_out.append(dates[ix])

    rises_out = pd.DataFrame({'rise': rises_out})    
    sets_out = pd.DataFrame({'set': sets_out})   

    rises_out = pd.to_datetime(rises_out['rise'], format='%Y/%m/%d %H:%M:%S') + pd.Timedelta(hours=TIMEZONEOFFSET_H)    
    sets_out = pd.to_datetime(sets_out['set'], format = '%Y/%m/%d %H:%M:%S') + pd.Timedelta(hours=TIMEZONEOFFSET_H)

    #return times in akst, i.e. utc - 9 hours
    return (rises_out, sets_out)


if __name__ == '__main__':
    """Main script"""

    logging.debug("Loading templates")
    template = load_template()

    logging.debug("Parsing arguments")
    args = parse_arguments()

    # set output directory
    output_dir = args.dir
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    logging.debug("Starting to retrieve station data from ACIS")
    meta = get_acis_stn_latlon(stationtype=int(args.type))
    stations = meta.keys()
    daterange = pd.date_range(start= '2018-01-01 00:00', end = '2018-12-31 00:00')

    times = {}
    for station in stations: 
        times[station] = pd.DataFrame(columns=['dates'])
        times[station]['dates'] = pd.date_range(start='2018-01-01 00:00', end='2018-12-31 23:59')

    logging.debug("Starting work on template variables")

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
    for station in stations:
        stationObs = ephem.Observer()

        logging.debug("generating items for {}".format(station))
        times[station]['sunrise'], times[station]['sunset'] = rise_set(
            horizonDay, False, stationObs, 
            meta[station]['lat'], meta[station]['lon'], times[station]['dates'])
        times[station]['civil_rise'], times[station]['civil_set'] = rise_set(
            horizonCivil, True, stationObs, 
            meta[station]['lat'], meta[station]['lon'], times[station]['dates'])
        times[station]['naut_rise'], times[station]['naut_set'] = rise_set(
            horizonNautical, True, stationObs, 
            meta[station]['lat'], meta[station]['lon'], times[station]['dates'])
        times[station]['astr_rise'], times[station]['astr_set'] = rise_set(
            horizonAstronomical, True, stationObs, 
            meta[station]['lat'], meta[station]['lon'], times[station]['dates'])
            
        times[station].to_csv(os.path.join("testdir", ''.join(lett for lett in station if lett.isalnum())), sep='\t')
        seconds[station] = pd.DataFrame(columns = times[station].columns)

        #convert time values to number of milliseconds in day (this is what highcharts wants)
        for column in times[station].columns:

            seconds[station][column] = times[station][column].dt.hour * 3600 + times[station][column].dt.minute * 60 + times[station][column].dt.second
            seconds[station][column] = seconds[station][column] * 1000

            #this adds a day if sunset is before noon
            seconds[station].loc[seconds[station]['civil_set'] < 12 * 3600 * 1000, 'civil_set'] = seconds[station]['civil_set'] + 24 * 3600 * 1000
            seconds[station].loc[seconds[station]['naut_set'] < 12 * 3600 * 1000, 'naut_set'] = seconds[station]['naut_set'] + 24 * 3600 * 1000
            seconds[station].loc[seconds[station]['astr_set'] < 12 * 3600 * 1000, 'astr_set'] = seconds[station]['astr_set'] + 24 * 3600 * 1000
            seconds[station].loc[seconds[station]['sunset'] < 12 * 3600 * 1000, 'sunset'] = seconds[station]['sunset'] + 24 * 3600 * 1000

        #day of year in millisecons for x axis
        seconds[station]['num'] = (seconds[station].index + 1) * 24 * 3600 * 1000

    ## various attempts to fiddle with settings to fix the gaps
        AM = seconds[station]['astr_rise'].min()
        PM = seconds[station]['astr_set'].max()

        seconds[station]['zeroAM'] = 0
        seconds[station]['zeroPM'] = (24 * 3600 * 1000) - 1
        # make strings to pass to highcharts. format: [xData, yData low end of range, yData high end of range]
        string_day[station] = makeRange(seconds[station]['num'], seconds[station]['sunrise'], seconds[station]['sunset'])
        string_civilAM[station] = makeRange(seconds[station]['num'], seconds[station]['civil_rise'], seconds[station]['sunrise'])
        string_civilPM[station] = makeRange(seconds[station]['num'], seconds[station]['sunset'], seconds[station]['civil_set'])
        string_nautAM[station] = makeRange(seconds[station]['num'], seconds[station]['naut_rise'], seconds[station]['civil_rise'])
        string_nautPM[station] = makeRange(seconds[station]['num'], seconds[station]['civil_set'], seconds[station]['naut_set'])
        string_astrAM[station] = makeRange(seconds[station]['num'], seconds[station]['astr_rise'], seconds[station]['naut_rise'])
        string_astrPM[station] = makeRange(seconds[station]['num'], seconds[station]['naut_set'], seconds[station]['astr_set'])
        string_nightAM[station] = makeRange(seconds[station]['num'], seconds[station]['zeroAM'], seconds[station]['astr_rise'])
        string_nightPM[station] = makeRange(seconds[station]['num'], seconds[station]['astr_set'], seconds[station]['zeroPM'])

    #build variable to give to highcharts
    template_vars = {}
    for station in stations:
        name = ''.join(lett for lett in station if lett.isalnum())
        template_vars[name + 'Day'] = string_day[station]
        template_vars[name + 'Civil_twilight_AM'] = string_civilAM[station]
        template_vars[name + 'Civil_twilight_PM'] = string_civilPM[station]
        template_vars[name + 'Nautical_twilight_AM'] = string_nautAM[station]
        template_vars[name + 'Nautical_twilight_PM'] = string_nautPM[station]
        template_vars[name + 'Astro_twilight_AM'] = string_astrAM[station]
        template_vars[name + 'Astro_twilight_PM'] = string_astrPM[station]
        template_vars[name + 'Night_AM'] = string_nightAM[station]
        template_vars[name + 'Night_PM'] = string_nightPM[station]

    #pass to highcharts template
    output_file = os.path.join(output_dir, OUTPUTFN)
    with open(output_file, 'w') as handle:
        handle.write(template.render(template_vars))
