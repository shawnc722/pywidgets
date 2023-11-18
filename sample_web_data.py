from pywidgets.sample_data import *
from pywidgets.external_sources import weather_icons
from requests import get


def ip_api_req(field: str):
    return PyCmd(get, 'http://ip-api.com/json/', params=dict(fields=field), postformat_fn=lambda x: x.json()[field])


def weather_api_req(params: dict, getkeys=('hourly', 'precipitation_probability'), addtz='auto'):
    newparams = params.copy()
    newparams['latitude'] = ip_cmds['lat']()
    newparams['longitude'] = ip_cmds['lon']()
    if addtz is not None: newparams['timezone'] = addtz

    def f(r):
        last = r.json()
        for key in getkeys: last = last[key]
        return last

    return PyCmd(get, 'https://api.open-meteo.com/v1/forecast', params=newparams, postformat_fn=f)


def get_weather_icon(code: int | str = 53, day=True):
    """Given a WMO weather interpretation code, returns the weather description and the icon in bytes.
    :code: WMO weather interpretation code.
    :night: whether to use the day variant of the icon.
    :returns: (short description of the weather, requests.Response containing the icon)"""
    node = weather_icons[str(code)][('night', 'day')[day]]
    return node['description'], get(node['image']).content


ip_cmds = {field: ip_api_req(field) for field in
           'continent,continentCode,country,countryCode,region,regionName,city,district,zip,lat,lon,query'.split(',')}

weather_cmds = {
    'hourly precipitation chance':  # returns a list of the percentages from 12:00AM today
        weather_api_req(dict(hourly='precipitation_probability', forecast_days=1)),
    'get icon':  # takes a WMO weather interpretation code and returns the corresponding icon from openweathermap.org
        PyCmd(get_weather_icon),
    'daily weathercodes':
        weather_api_req(dict(daily='weathercode'), getkeys=('daily', 'weathercode')),
    'current weather':
        weather_api_req(dict(current_weather=True, forecast_days=0), getkeys=('current_weather',))
}

web_cmds = {
    "ip cmds": ip_cmds,
    "weather cmds": weather_cmds
}
