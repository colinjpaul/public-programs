import requests, sys, os, pytz
from datetime import datetime, date, timedelta
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

LOCAL_TIMEZONE = pytz.timezone('Asia/Calcutta')
FITBIT_LANGUAGE = 'en_US'
FITBIT_CLIENT_ID = ''
FITBIT_CLIENT_SECRET = ''
FITBIT_ACCESS_TOKEN = 'OAuth Token'
FITBIT_INITIAL_CODE = ''
REDIRECT_URI = 'https://localhost'
INFLUXDB_HOST = 'localhost'
INFLUXDB_PORT = 8086
INFLUXDB_USERNAME = 'arpan'
INFLUXDB_PASSWORD = '#Password#1'
INFLUXDB_DATABASE = 'fitbit'
points = []

#dates variable assignment

#start_date = '2021-04-01'
#end_date = '2021-04-05'

print("\n=====================Manual influxdb update====================\n")

start_date = input("Enter start date (yyyy-mm-dd format ) : ")
end_date = input("Enter end date + 1 (yyyy-mm-dd format ) : ")

print("\n=====================Starting Update====================\n")


def fetch_data(category, type, date_var):
    try:
        response = requests.get('https://api.fitbit.com/1/user/-/' + category + '/' + type + '/date/'+date_var+'/1d.json', 
            headers={'Authorization': 'Bearer ' + FITBIT_ACCESS_TOKEN, 'Accept-Language': FITBIT_LANGUAGE})
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print("HTTP request failed: %s" % (err))
        sys.exit()

    data = response.json()
    print("Got " + type + " for "+ date_var +" from Fitbit")

    for day in data[category.replace('/', '-') + '-' + type]:
        points.append({
                "measurement": type,
                "time": LOCAL_TIMEZONE.localize(datetime.fromisoformat(day['dateTime'])).astimezone(pytz.utc).isoformat(),
                "fields": {
                    "value": float(day['value'])
                }
            })

def fetch_heartrate(date):
    try:
        response = requests.get('https://api.fitbit.com/1/user/-/activities/heart/date/' + date + '/1d/1sec.json', 
            headers={'Authorization': 'Bearer ' + FITBIT_ACCESS_TOKEN, 'Accept-Language': FITBIT_LANGUAGE})
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print("HTTP request failed: %s" % (err))
        sys.exit()

    data = response.json()
    print("Got heartrates for "+date+" from Fitbit")

    for day in data['activities-heart']:
        if 'restingHeartRate' in day['value']:
            points.append({
                    "measurement": "restingHeartRate",
                    "time": datetime.fromisoformat(day['dateTime']),
                    "fields": {
                        "value": float(day['value']['restingHeartRate'])
                    }
                })

        if 'heartRateZones' in day['value']:
            for zone in day['value']['heartRateZones']:
                if 'caloriesOut' in zone and 'min' in zone and 'max' in zone and 'minutes' in zone:
                    points.append({
                            "measurement": "heartRateZones",
                            "time": datetime.fromisoformat(day['dateTime']),
                            "tags": {
                                "zone": zone['name']
                            },
                            "fields": {
                                "caloriesOut": float(zone['caloriesOut']),
                                "min": float(zone['min']),
                                "max": float(zone['max']),
                                "minutes": float(zone['minutes'])
                            }
                        })
                elif 'min' in zone and 'max' in zone and 'minutes' in zone:
                    points.append({
                            "measurement": "heartRateZones",
                            "time": datetime.fromisoformat(day['dateTime']),
                            "tags": {
                                "zone": zone['name']
                            },
                            "fields": {
                                "min": float(zone['min']),
                                "max": float(zone['max']),
                                "minutes": float(zone['minutes'])
                            }
                        })

    if 'activities-heart-intraday' in data:
        for value in data['activities-heart-intraday']['dataset']:
            time = datetime.fromisoformat(date + "T" + value['time'])
            utc_time = LOCAL_TIMEZONE.localize(time).astimezone(pytz.utc).isoformat()
            points.append({
                    "measurement": "heartrate",
                    "time": utc_time,
                    "fields": {
                        "value": float(value['value'])
                    }
                })

def process_levels(levels):
    for level in levels:
        type = level['level']
        if type == "asleep":
            type = "light"
        if type == "restless":
            type = "rem"
        if type == "awake":
            type = "wake"

        time = datetime.fromisoformat(level['dateTime'])
        utc_time = LOCAL_TIMEZONE.localize(time).astimezone(pytz.utc).isoformat()
        points.append({
                "measurement": "sleep_levels",
                "time": utc_time,
                "fields": {
                    "seconds": int(level['seconds'])
                }
            })

def fetch_activities(date):
    try:
        response = requests.get('https://api.fitbit.com/1/user/-/activities/list.json',
            headers={'Authorization': 'Bearer ' + FITBIT_ACCESS_TOKEN, 'Accept-Language': FITBIT_LANGUAGE},
            params={'beforeDate': date, 'sort':'desc', 'limit':10, 'offset':0})
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print("HTTP request failed: %s" % (err))
        sys.exit()

    data = response.json()
    print("Got activities from Fitbit for before_date: "+date)

    for activity in data['activities']:
        fields = {}

        if 'activeDuration' in activity:
            fields['activeDuration'] = int(activity['activeDuration'])
        if 'averageHeartRate' in activity:
            fields['averageHeartRate'] = int(activity['averageHeartRate'])
        if 'calories' in activity:
            fields['calories'] = int(activity['calories'])
        if 'duration' in activity:
            fields['duration'] = int(activity['duration'])
        if 'distance' in activity:
            fields['distance'] = float(activity['distance'])
            fields['distanceUnit'] = activity['distanceUnit']
        if 'pace' in activity:
            fields['pace'] = float(activity['pace'])
        if 'speed' in activity:
            fields['speed'] = float(activity['speed'])
        if 'elevationGain' in activity:
            fields['elevationGain'] = int(activity['elevationGain'])
        if 'steps' in activity:
            fields['steps'] = int(activity['steps'])

        for level in activity['activityLevel']:
            if level['name'] == 'sedentary':
                fields[level['name'] + "Minutes"] = int(level['minutes'])
            else:
                fields[level['name'] + "ActiveMinutes"] = int(level['minutes'])


        time = datetime.fromisoformat(activity['startTime'].strip("Z"))
        utc_time = time.astimezone(pytz.utc).isoformat()
        points.append({
            "measurement": "activity",
            "time": utc_time,
            "tags": {
                "activityName": activity['activityName']
            },
            "fields": fields
        })

try:
    client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USERNAME, password=INFLUXDB_PASSWORD)
    client.create_database(INFLUXDB_DATABASE)
    client.switch_database(INFLUXDB_DATABASE)
except InfluxDBClientError as err:
    print("InfluxDB connection failed: %s" % (err))
    sys.exit()

if not FITBIT_ACCESS_TOKEN:
    if os.path.isfile('.fitbit-refreshtoken'):
        f = open(".fitbit-refreshtoken", "r")
        token = f.read()
        f.close()
        response = requests.post('https://api.fitbit.com/oauth2/token',
            data={
                "client_id": FITBIT_CLIENT_ID,
                "grant_type": "refresh_token",
                "redirect_uri": REDIRECT_URI,
                "refresh_token": token
            }, auth=(FITBIT_CLIENT_ID, FITBIT_CLIENT_SECRET))
    else:
        response = requests.post('https://api.fitbit.com/oauth2/token',
            data={
                "client_id": FITBIT_CLIENT_ID,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
                "code": FITBIT_INITIAL_CODE
            }, auth=(FITBIT_CLIENT_ID, FITBIT_CLIENT_SECRET))

    response.raise_for_status()

    json = response.json()
    FITBIT_ACCESS_TOKEN = json['access_token']
    refresh_token = json['refresh_token']
    f = open(".fitbit-refreshtoken", "w+")
    f.write(refresh_token)
    f.close()

try:
    response = requests.get('https://api.fitbit.com/1/user/-/devices.json', 
        headers={'Authorization': 'Bearer ' + FITBIT_ACCESS_TOKEN, 'Accept-Language': FITBIT_LANGUAGE})
    response.raise_for_status()
except requests.exceptions.HTTPError as err:
    print("HTTP request failed: %s" % (err))
    sys.exit()

data = response.json()
print("Got devices from Fitbit for current datetime "+str(datetime.today()))

for device in data:
    points.append({
        "measurement": "deviceBatteryLevel",
        "time": LOCAL_TIMEZONE.localize(datetime.fromisoformat(device['lastSyncTime'])).astimezone(pytz.utc).isoformat(),
        "tags": {
            "id": device['id'],
            "deviceVersion": device['deviceVersion'],
            "type": device['type'],
            "mac": device['mac'],
        },
        "fields": {
            "value": float(device['batteryLevel'])
        }
    })


#Sleep logs

print("\n=====================Updating sleep log database====================\n")

try:
    response = requests.get('https://api.fitbit.com/1.2/user/-/sleep/date/' + start_date + '/' + end_date + '.json',
        headers={'Authorization': 'Bearer ' + FITBIT_ACCESS_TOKEN, 'Accept-Language': FITBIT_LANGUAGE})
    response.raise_for_status()
except requests.exceptions.HTTPError as err:
    print("HTTP request failed: %s" % (err))
    sys.exit()

data = response.json()
print("Got sleep sessions from Fitbit")

for day in data['sleep']:
    time = datetime.fromisoformat(day['startTime'])
    utc_time = LOCAL_TIMEZONE.localize(time).astimezone(pytz.utc).isoformat()
    if day['type'] == 'stages':
        points.append({
            "measurement": "sleep",
            "time": utc_time,
            "fields": {
                "duration": int(day['duration']),
                "efficiency": int(day['efficiency']),
                "is_main_sleep": bool(day['isMainSleep']),
                "minutes_asleep": int(day['minutesAsleep']),
                "minutes_awake": int(day['minutesAwake']),
                "time_in_bed": int(day['timeInBed']),
                "minutes_deep": int(day['levels']['summary']['deep']['minutes']),
                "minutes_light": int(day['levels']['summary']['light']['minutes']),
                "minutes_rem": int(day['levels']['summary']['rem']['minutes']),
                "minutes_wake": int(day['levels']['summary']['wake']['minutes']),
            }
        })
    else:
        points.append({
            "measurement": "sleep",
            "time": utc_time,
            "fields": {
                "duration": int(day['duration']),
                "efficiency": int(day['efficiency']),
                "is_main_sleep": bool(day['isMainSleep']),
                "minutes_asleep": int(day['minutesAsleep']),
                "minutes_awake": int(day['minutesAwake']),
                "time_in_bed": int(day['timeInBed']),
                "minutes_deep": 0,
                "minutes_light": int(day['levels']['summary']['asleep']['minutes']),
                "minutes_rem": int(day['levels']['summary']['restless']['minutes']),
                "minutes_wake": int(day['levels']['summary']['awake']['minutes']),
            }
        })
    
    if 'data' in day['levels']:
        process_levels(day['levels']['data'])
    
    if 'shortData' in day['levels']:
        process_levels(day['levels']['shortData'])

print("\n=====================Sleep logs updated====================\n")


start = datetime.strptime(start_date, "%Y-%m-%d")
end = datetime.strptime(end_date, "%Y-%m-%d")

date_array = (start + timedelta(days=x) for x in range(0, (end-start).days))

day_list = []
for date_object in date_array:
    day_list.append(date_object.strftime("%Y-%m-%d"))

iteration_count = 0

for day_date in day_list:

    fetch_data('activities', 'steps', day_date )
    fetch_data('activities', 'distance', day_date)
    fetch_data('activities', 'floors', day_date)
    fetch_data('activities', 'elevation', day_date)
    fetch_data('activities', 'distance', day_date)
    fetch_data('activities', 'minutesSedentary', day_date)
    fetch_data('activities', 'minutesLightlyActive', day_date)
    fetch_data('activities', 'minutesFairlyActive', day_date)
    fetch_data('activities', 'minutesVeryActive', day_date)
    fetch_data('activities', 'calories', day_date)
    fetch_data('activities', 'activityCalories', day_date)
    fetch_data('body', 'weight', day_date)
    fetch_data('body', 'fat', day_date)
    fetch_data('body', 'bmi', day_date)
    fetch_data('foods/log', 'water', day_date)
    fetch_data('foods/log', 'caloriesIn', day_date)
    fetch_heartrate(day_date)
    fetch_activities((datetime.strptime(day_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"))

    try:
        client.write_points(points)
    except InfluxDBClientError as err:
        print("Unable to write points to InfluxDB: %s" % (err))
        sys.exit()

    print("Successfully wrote %s data points to InfluxDB" % (len(points)))

    print("\n=============================== O ===============================\n")

    iteration_count += 1
    if iteration_count % 5 == 0:
        print("\n--------------Assuming API limit reached : Pausing script for an hour-----------------\n")
        time.sleep(3660)