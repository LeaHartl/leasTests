import requests
import urllib.request
import re
import calendar
import datetime
import dateutil.parser as parser
import textwrap
import matplotlib.colors as colors
import numpy as np
from collections import deque



# read data from REST endpoint
def read_data( url, params, header="" ):
  resq = requests.get(url, headers=header, params=params)
  # print( resq.url )
  return resq.json()

# read file from url endpoint
def read_file( url, params ):
  comurl = url
  for key, param in params.items():
    comurl = comurl + key + "=" + param + "&"
  # print( comurl )
  response = urllib.request.urlopen(comurl)
  data = response.read()      # a `bytes` object
  text = data.decode('utf-8') # a `str`; this step can't be used if data is binary

  return text

# calculate month start and end
def cal_month(date = ""):
  if date == "":
    current_year = datetime.datetime.now().strftime("%Y")
    current_month = datetime.datetime.now().strftime("%m")
  else:
    date_split = date.split("-")
    current_year = date_split[0]
    current_month = date_split[1]

  last_day = calendar.monthrange(int(current_year), int(current_month))[1]

  return( current_year, current_month, str(last_day), calendar.month_name[int(current_month)] )

# extract month extremes from year dataset
def month_extremes(sdate, last_day, data):
  first_day = parser.parse(sdate).timetuple().tm_yday
  month_data = []

  for cnt in range(first_day, first_day + int(last_day)):
    month_data.append(data[cnt])

  return(month_data)

# convert Fahrenheit to Celsius
def to_cels(value):
  return (value - 32) * 5.0/9.0

# convert Fahrenheit to Celsius increment
def to_cels_inc(value):
  return value / 1.8

# extract month high and low from month data
def month_high_low(data):
  month_data = [-100.0, 300.0, "", ""]

  for index, value in enumerate(data[1]):
    if value != "t" and value != "M":
      if month_data[0] <= float(value):
        month_data[0] = float(value)         # set low temp
        month_data[2] = index + 1            # set low date

  for index, value in enumerate(data[2]):
    if value != "t" and value != "M":
      if month_data[1] >= float(value):
        month_data[1] = float(value)         # set high temp
        month_data[3] = index + 1            # set high date

  return(month_data)

  # Build monthly weather information about a city
def build_info(mean_temp, mean_norm, highist, high_date, lowest, low_date, precip, precip_norm):
  if mean_temp == "M": mean_temp = np.nan
  if precip == "M": precip = '0.00'
  print(precip)

  temp_diff = float(mean_temp) - float(mean_norm)
  tdiff = str(temp_diff)

  if temp_diff>0.0:
    diff_text = str("%.1f" % temp_diff) + "°F above normal."
  elif temp_diff == 0.0:
    diff_text = "the same as the normal."
  else:
    diff_text = str("%.1f" % abs(temp_diff)) + "°F below normal."

  precip_diff = float(precip) - float(precip_norm)
  pdiff = str(precip_diff)

  if precip_diff>0.0:
    precip_text = str("%.1f" % precip_diff) + "\" above normal."
  elif precip_diff == 0.0:
    precip_text = "the same as the normal."
  else:
    precip_text = str("%.1f" % abs(precip_diff)) + "\" below normal."

  hd_check = abs(high_date) % 10
  if hd_check == 1:
    high_post = "st"
  elif hd_check == 2:
    high_post = "nd"
  elif hd_check == 3:
    high_post = "rd"
  else:
    high_post = "th"

  ld_check = abs(low_date) % 10
  if ld_check == 1:
    low_post = "st"
  elif ld_check == 2:
    low_post = "nd"
  elif ld_check == 3:
    low_post = "rd"
  else:
    low_post = "th"

  text = textwrap.dedent("""\
  <table>
    <tr>
      <td>
        Mean monthly temperature was {0}°F, which was {1}
     </td>
    </tr>
    <tr>
      <td>
        The observed maximum temperature was {2}°F on the {3}{4} of the month,<br/>
        the minimum temperature was {5}°F on the {6}{7} of the month.
      </td>
    </tr>
    <tr>
      <td>
        The total monthly precipitation was {8}", which was {9}
      </td>
    </tr>
    <tr>
      <td>
        Note: Normal values refer to the period 1981 to 2010.
      </td>
    </tr>
  </table>
  """)
  
  # if precip == 0.0: return ""
  #  return text.format(mean_temp[:-1], diff_text, highist, high_date, high_post, lowest, low_date, low_post, precip[:-1], precip_text)
  return text.format(mean_temp, diff_text, highist, high_date, high_post, lowest, low_date, low_post, str(np.round(float(precip), decimals = 1)), precip_text)

# rotate values in a list
def rotate(lst, x):
  d = deque(lst)
  d.rotate(x)
  lst[:] = d
 
# process ACIS data for missing or trace values and convert from string
# takes a list as a parameter and a string type (int or float)
def proc_acis(data, type):
  new_list = []

  for item in data:
    if item == "M":
      new_list.append(np.nan)
    elif item == "T":
      new_list.append(0.0)
    else:
      if type == "float": new_list.append(float(item))
      if type == "int": new_list.append(int(item))

  return new_list

# set the colormap and center the colorbar
class MidpointNormalize(colors.Normalize):
  """
  Normalise the colorbar so that diverging bars work there way either side from a prescribed midpoint value)

  e.g. im=ax1.imshow(array, norm=MidpointNormalize(midpoint=0.,vmin=-100, vmax=100))
  """
  def __init__(self, vmin=None, vmax=None, midpoint=None, clip=False):
    self.midpoint = midpoint
    colors.Normalize.__init__(self, vmin, vmax, clip)

  def __call__(self, value, clip=None):
    # I'm ignoring masked values and all kinds of edge cases to make a
    # simple example...
    x, y = [self.vmin, self.midpoint, self.vmax], [0, 0.5, 1]
    return np.ma.masked_array(np.interp(value, x, y), np.isnan(value))

def makeString(data):

  # maxN_list = []
  data= data.tolist()
  # data = dh.makeString(tmpN_list) 

  convert = ""
  for item in data:
    if np.isnan(item) : item = 'null'
    convert += str(item) + ',' 
  return convert[:-1]

 
