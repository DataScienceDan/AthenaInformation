import re
import json
import urllib.request
from datetime import datetime, timedelta

# Read API token
with open('ToDoToken.txt', 'r') as f:
    lines = f.readlines()
    api_token = lines[1].strip()

# Read input file
with open('Input.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Helper to parse time windows
def parse_time_window(time_str):
    # Handles formats like '8:00am', '9:00-9:30am', '11:30-1:00pm'
    time_window_pattern = r'(\d{1,2}:\d{2}(?:am|pm)?)(?:-(\d{1,2}:\d{2}(?:am|pm)?))?'
    match = re.match(time_window_pattern, time_str)
    if not match:
        return None, None
    start, end = match.groups()
    return start, end

# Extract daily and weekly events
daily_events = []
weekly_events = []

# Find Daily section
daily_section = re.search(r'Daily:[\r\n]+((?:- .+\n)+)', content)
if daily_section:
    for line in daily_section.group(1).splitlines():
        m = re.match(r'- (\d{1,2}:\d{2}(?:am|pm)?(?:-\d{1,2}:\d{2}(?:am|pm)?)?): (.+)', line)
        if m:
            time_window, desc = m.groups()
            start, end = parse_time_window(time_window)
            daily_events.append({'start': start, 'end': end, 'desc': desc})

# Find Weekly section
weekly_section = re.search(r'Weekly:[\r\n]+((?:- .+\n)+)', content)
if weekly_section:
    for line in weekly_section.group(1).splitlines():
        m = re.match(r'- (Week \d+): (.+)', line)
        if m:
            week, desc = m.groups()
            weekly_events.append({'week': week, 'desc': desc})

# Helper to create a Todoist task
def create_todoist_task(content, due_string=None):
    url = 'https://api.todoist.com/rest/v2/tasks'
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json',
    }
    data = {'content': content}
    if due_string:
        data['due_string'] = due_string
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode()
    except Exception as e:
        print(f'Error creating task: {e}')
        return None

# Insert daily events (assume today for demo)
today = datetime.now().strftime('%Y-%m-%d')
for event in daily_events:
    desc = event['desc']
    start = event['start']
    end = event['end']
    if start:
        due_string = f"today at {start}"
        if end:
            desc = f"{desc} ({start} - {end})"
    else:
        due_string = "today"
    print(f'Creating daily task: {desc} ({due_string})')
    create_todoist_task(desc, due_string)

# Insert weekly events (assume next 4 Mondays for demo)
for idx, event in enumerate(weekly_events):
    desc = f"{event['week']}: {event['desc']}"
    # Schedule for next N Mondays
    next_monday = (datetime.now() + timedelta(days=(7 - datetime.now().weekday()) % 7 + 7*idx)).strftime('%Y-%m-%d')
    due_string = f"{next_monday}"
    print(f'Creating weekly task: {desc} ({due_string})')
    create_todoist_task(desc, due_string) 