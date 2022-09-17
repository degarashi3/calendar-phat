#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
import datetime, re
import os
import json
import requests
import googleapiclient.discovery
import google.auth

from inky.auto import auto
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
from font_fredoka_one import FredokaOne
from pathlib import Path

print("""Inky pHAT: Calendar

Draws a calendar for the current month to your Inky pHAT.
This example uses a sprite sheet of numbers and month names which are
composited over the background in a couple of different ways.

""")

# Get the current path

PATH = os.path.dirname(__file__)
font = ImageFont.truetype("NotoSansCJK-Regular.ttc", 10)

# Set up the display
try:
    inky_display = auto(ask_user=True, verbose=True)
except TypeError:
    raise TypeError("You need to update the Inky library to >= v1.1.0")


if inky_display.resolution not in ((212, 104), (250, 122)):
    w, h = inky_display.resolution
    raise RuntimeError("This example does not support {}x{}".format(w, h))

inky_display.set_border(inky_display.BLACK)

# Uncomment the following if you want to rotate the display 180 degrees
# inky_display.h_flip = True
# inky_display.v_flip = True


def create_mask(source, mask=(inky_display.WHITE, inky_display.BLACK, inky_display.RED)):
    """Create a transparency mask.

    Takes a paletized source image and converts it into a mask
    permitting all the colours supported by Inky pHAT (0, 1, 2)
    or an optional list of allowed colours.
    :param mask: Optional list of Inky pHAT colours to allow.
    """
    mask_image = Image.new("1", source.size)
    w, h = source.size
    for x in range(w):
        for y in range(h):
            p = source.getpixel((x, y))
            if p in mask:
                mask_image.putpixel((x, y), 255)

    return mask_image


def print_digit(position, digit, colour):
    """Print a single digit using the sprite sheet.

    Each number is grabbed from the masked sprite sheet,
    and then used as a mask to paste the desired colour
    onto Inky pHATs image buffer.
    """
    o_x, o_y = position

    num_margin = 2
    num_width = 6
    num_height = 7

    s_y = 11
    s_x = num_margin + (digit * (num_width + num_margin))

    sprite = text_mask.crop((s_x, s_y, s_x + num_width, s_y + num_height))

    img.paste(colour, (o_x, o_y), sprite)


def print_number(position, number, colour):
    """Print a number using the sprite sheet."""
    for digit in str(number):
        print_digit(position, int(digit), colour)
        position = (position[0] + 8, position[1])

def get_events():
    # Preparation for Google API
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    calendar_id = 'hiroki.akiyama@gmail.com'
    carendar_id_work = 'ljs562ls522uppmln7pv3pllb4@group.calendar.google.com'
    gapi_creds = google.auth.load_credentials_from_file('/home/pi/pi-calendar/credentials.json', SCOPES)[0]
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=gapi_creds)

    # Get events from Google Calendar API
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
         calendarId=calendar_id, timeMin=now,
         maxResults=3, singleEvents=True,
         orderBy='startTime').execute()

    work_events_result = service.events().list(
         calendarId=carendar_id_work, timeMin=now,
         maxResults=3, singleEvents=True,
         orderBy='startTime').execute()

    # Pick up only start time, end time and summary info
    events = events_result.get('items', []) + work_events_result.get('items', [])
    #events = sorted(events.items('start'))
    formatted_events = [(event['start'].get('dateTime', event['start'].get('date')), # start time or day
         event['end'].get('dateTime', event['end'].get('date')), # end time or day
         event['summary']) for event in events]
    formatted_events = sorted(formatted_events)

    # Generate output text
    response = ''
    for event in formatted_events:
         if re.match(r'^\d{4}-\d{2}-\d{2}$', event[0]):
             start_date = '{0:%Y-%m-%d}'.format(datetime.strptime(event[1], '%Y-%m-%d') + timedelta(days=-1))
             response += '{0} 終日\n {1}\n'.format(start_date, event[2][:9])
         # For all day events
         else:
             start_time = '{0:%m/%d %H:%M}'.format(datetime.strptime(event[0], '%Y-%m-%dT%H:%M:%S+09:00'))
             end_time = '{0:%H:%M}'.format(datetime.strptime(event[1], '%Y-%m-%dT%H:%M:%S+09:00'))
             response += '{0}~{1}\n {2}\n'.format(start_time, end_time, event[2][:9])
    response = response.rstrip('\n')

    return response

# イベントが更新されてなかったら終了
my_events = get_events();

f_path = '/home/pi/pi-calendar/current_events.txt'

mtime =  os.path.getmtime(Path(f_path))
mod_date = datetime.fromtimestamp(mtime)
now = datetime.now()

if not os.path.isfile(f_path):
    with open(f_path, 'w'):
        pass

with open(f_path) as f:
    current = f.read()
    if ((mod_date.year, mod_date.month, mod_date.day) == (now.year, now.month, now.day)) :
            if (current == my_events):
                quit()

with open(f_path, mode='w') as f:
   f.write(my_events)

# Load our sprite sheet and prepare a mask
text = Image.open(os.path.join(PATH, "resources/calendar.png"))
text_mask = create_mask(text, [inky_display.WHITE])

response = requests.get('https://holidays-jp.github.io/api/v1/date.json')
holidays = json.loads(response.text)

# Note: The mask determines which pixels from our sprite sheet we want
# to actually use when calling img.paste().
# See: http://pillow.readthedocs.io/en/3.1.x/reference/Image.html?highlight=paste#PIL.Image.Image.paste

# Load our backdrop image
img = Image.open(os.path.join(PATH, "resources/simple.png")).resize(inky_display.resolution)
draw = ImageDraw.Draw(img)

# Grab the current date, and prepare our calendar
cal = calendar.Calendar()
cal.setfirstweekday(calendar.SUNDAY)
dates = cal.monthdatescalendar(now.year, now.month)

col_w = 20
col_h = 18

cols = 7
rows = len(dates) + 1

cal_w = 1 + ((col_w + 1) * cols)
cal_h = 1 + ((col_h + 1) * rows)

cal_x = inky_display.WIDTH - cal_w - 2
cal_y = 2

# Paint out a black rectangle onto which we'll draw our canvas
draw.rectangle((cal_x, cal_y, cal_x + cal_w - 1, cal_y + cal_h - 1), fill=inky_display.BLACK, outline=inky_display.WHITE)

# The starting position of the months in our spritesheet
months_x = 2
months_y = 20

# Number of months per row
months_cols = 3

# The width/height of each month in our spritesheet
month_w = 23
month_h = 9

# Figure out where the month is in the spritesheet
month_col = (now.month - 1) % months_cols
month_row = (now.month - 1) // months_cols

# Convert that location to usable X/Y coordinates
month_x = months_x + (month_col * month_w)
month_y = months_y + (month_row * month_h)

crop_region = (month_x, month_y, month_x + month_w, month_y + month_h)

month = text.crop(crop_region)
month_mask = text_mask.crop(crop_region)

monthyear_x = 2

# Paste in the month name we grabbed from our sprite sheet
img.paste(inky_display.WHITE, (monthyear_x, cal_y + 4), month_mask)

# Print the year right below the month
#print_number((monthyear_x, cal_y + 5 + col_h), now.year, inky_display.WHITE)
print_number((monthyear_x + 25, cal_y + 4), now.year, inky_display.WHITE)

# Draw the vertical lines which separate the columns
# and also draw the day names into the table header
for x in range(cols):
    # Figure out the left edge of the column
    o_x = (col_w + 1) * x
    o_x += cal_x

    crop_x = 2 + (16 * x) - 16

    if (x == 0):
        crop_x = 2 + (16 * 6)

    # Crop the relevant day name from our text image
    crop_region = ((crop_x, 0, crop_x + 16, 9))
    day_mask = text_mask.crop(crop_region)
    img.paste(inky_display.WHITE, (o_x + 4, cal_y + 4), day_mask)

    # Offset to the right side of the column and draw the vertical line
    o_x += col_w + 1
    draw.line((o_x, cal_y, o_x, cal_h))

# Draw the horizontal lines which separate the rows
for y in range(rows):
    o_y = (col_h + 1) * y
    o_y += cal_y + col_h + 1
    draw.line((cal_x, o_y, cal_w + cal_x - 1, o_y))

# Step through each week
for row, week in enumerate(dates):
    y = (col_h + 1) * (row + 1)
    y += cal_y + 1

    # And each day in the week
    for col, day in enumerate(week):
        x = (col_w + 1) * col
        x += cal_x + 1

        # Draw in the day name.
        # If it's the current day, invert the calendar background and text
        if (day.day, day.month) == (now.day, now.month):
            draw.rectangle((x, y, x + col_w - 1, y + col_h - 1), fill=inky_display.WHITE)
            if ( datetime(day.year, day.month, day.day).strftime("%Y-%m-%d") in holidays):
                print_number((x + 3, y + 5), day.day, inky_display.RED)
            elif (day.weekday() > 4):
                print_number((x + 3, y + 5), day.day, inky_display.RED)
            else:
                print_number((x + 3, y + 5), day.day, inky_display.BLACK)

        elif ( datetime(day.year, day.month, day.day).strftime("%Y-%m-%d") in holidays):
            print_number((x + 3, y + 5), day.day, inky_display.RED)

        elif ((day.month) == (now.month) and day.weekday() > 4):
            print_number((x + 3, y + 5), day.day, inky_display.RED)


        # If it's any other day, paint in as white if it's in the current month
        # and red if it's in the previous or next month
        elif (day.month) == (now.month):
#            print_number((x + 3, y + 3), day.day, inky_display.WHITE if day.month == now.month else inky_display.RED)
            print_number((x + 3, y + 5), day.day, inky_display.WHITE)

# イベントを書き込み
draw.text((2, 22), my_events, inky_display.WHITE, font=font)

# Display the completed calendar on Inky pHAT
inky_display.set_image(img)
inky_display.show()
