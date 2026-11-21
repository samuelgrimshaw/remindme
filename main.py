import datetime
import json
import caldav
from getpass import getpass
from zoneinfo import ZoneInfo
import uuid
from icalendar import Alarm
import argparse
import sys
from caldav.lib.error import AuthorizationError
from pathlib import Path
import keyring



DATA_DIR = Path(__file__).parent
EVENTS_FILE = DATA_DIR / 'events.json'
DELETED_FILE = DATA_DIR / 'deleted_events.json'

SERVICE_NAME = 'remindme'



def loadJson(path,default):
    try:
        with open(path,'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default
rawevents = loadJson(EVENTS_FILE,{})
pendingDeletes = loadJson(DELETED_FILE,[])
localEvents = {}

for eventId, details in rawevents.items():
    details['date'] = datetime.date.fromisoformat(details['date'])
    localEvents[int(eventId)] = details
eventNum = max(localEvents, default=0) + 1



#parse
def parseDate(text):
    return datetime.datetime.strptime(text,'%d%m%y').date()
def parseTime(text):
    return datetime.datetime.strptime(text,'%H%M').strftime('%H%M')


def makeAlarm(title,minutesBefore=60):
    alarm = Alarm()
    alarm.add('action','DISPLAY')
    alarm.add('description',title)
    alarm.add('trigger', datetime.timedelta(minutes=-minutesBefore))
    return alarm







#localEvents

def saveEvents():
    eventsToSave = {}
    for eventId, details in localEvents.items():
        savedDetails = details.copy()
        savedDetails['date'] = details['date'].isoformat()
        eventsToSave[eventId] = savedDetails

    with open(EVENTS_FILE, 'w') as f:
        json.dump(eventsToSave, f, indent=4)
    with open(DELETED_FILE,'w') as f:
        json.dump(pendingDeletes,f,indent=4)

    

def addEvent(desc,date,time,mod,freq,uid=None,syncedPrev=False):
    global eventNum

    
    localEvents[eventNum] = {
        'type':'R' if freq else 'O',
        'freq':freq,
        'date':date,
        'time':time,
        'mod':mod,
        'desc':desc,
        'uid': uid if uid else str(uuid.uuid4()),
        'needsUpdating' : False,
        'syncedPrev' : syncedPrev
    }
    eventNum += 1

    saveEvents()
def viewUpcomingEvent():
    currentDate = datetime.date.today()
    week = []
    month = []
    year = []
    for eventNum, details in sorted(localEvents.items(), key=lambda item: item[1]['date']):
        eventDate = details['date']
        diff = (eventDate - currentDate).days
        if 0 <= diff <= 7:
            week.append(eventNum)
        elif 7 < diff <= 30:
            month.append(eventNum)  
        elif 30 < diff <= 365:
            year.append(eventNum)
    if week:
        print('-----')
        print('Next 7 days')
        for event in week:
            viewEvent(event)
    if month:
        print('-----')
        print('Next 30 days')
        for event in month:
            viewEvent(event)
    if year:
        print('-----')
        print("Next 365 days")
        for event in year:
            viewEvent(event)




def deleteEvent(id):
    removedEvent = localEvents.pop(id,None)
    if removedEvent is None:
        print('Event not found')
        return
    if removedEvent.get('uid'):
        pendingDeletes.append(removedEvent['uid'])
    print(f'Record {id} has been deleted.')
    saveEvents()
    

def editEvent(id,field,value):
    if id not in localEvents:
        sys.exit('Invalid record number')
    if field == 'date':
        try:
            value = parseDate(value)
        except ValueError:
            sys.exit(f'{value} is an invalid date')
    elif field == 'time':
        try:
            value = parseTime(value)
        except ValueError:
            sys.exit(f'{value} is an invalid time')
    localEvents[id][field] = value
    localEvents[id]['needsUpdating'] = True
    saveEvents()
    print("Event edited.")

def getCredentials():
    email = input("Email: ")
    if keyring.get_password(SERVICE_NAME,email):
        password = keyring.get_password(SERVICE_NAME,email)
    else:
        password = getpass("Password: ")
    return (email,password)








# SYNC

def syncDeletes(deletes,existing):
    for uid in deletes:
        if uid in existing:
            existing[uid].delete()
            del existing[uid]
            print('Event deleted')
    deletes.clear()

def syncUpdates(start,title,UID,array):
    remoteEvent = array[UID]
    comp = remoteEvent.icalendar_component

    for field in ('summary','dtstart','dtend'):
        comp.pop(field,None)
    comp.add('summary', title)
    comp.add('dtstart',start)
    comp.add('dtend',start + datetime.timedelta(minutes=30))
    comp.subcomponents = [c for c in comp.subcomponents if c.name != 'VALARM']
    comp.add_component(makeAlarm(title))
    remoteEvent.save()
    print('Event updated')

def syncCreate(freq,start,title,eventUID,calendar):
    if freq is None:
        calendar.add_event(
            dtstart=start,
            dtend=start + datetime.timedelta(minutes=30),
            summary=title,
            uid=eventUID,
            alarm_trigger=datetime.timedelta(minutes=-60),
            alarm_action='DISPLAY',
            alarm_description=title
        )
    else:
        calendar.add_event(
            dtstart=start,
            dtend=start + datetime.timedelta(minutes=30),
            summary=title,
            uid=eventUID,
            rrule={'FREQ': freq},
            alarm_trigger=datetime.timedelta(minutes=-60),
            alarm_action='DISPLAY',
            alarm_description=title
        )
def findCalendar(client):
    calendars = client.get_calendars()
    calendarName = 'RemindMeNEW'

    matches = [
        calendar for calendar in calendars
        if calendar.get_display_name() == calendarName
    ]

    if not matches:
        sys.exit('No calendar found, check README to create a calendar.')
    
    return matches[0]

def syncEvents():
    email,password = getCredentials()
    try:
        with caldav.DAVClient(
            url="https://caldav.icloud.com/",
            username=email,
            password=password
            ) as client:
            calendar = findCalendar(client)
            currentEvents = calendar.get_events()

            # set password
            keyring.set_password(SERVICE_NAME,email,password)

            # create existing array
            globalUIDs = {}
            for event in currentEvents:
                globalUIDs[str(event.get_icalendar_component()['UID'])] = event

            # deleted localEvents
            syncDeletes(pendingDeletes,globalUIDs)

            localUIDs = set()

            localQueue = []

            for id,detail in localEvents.items():
                title = detail['desc']
                startTime = datetime.datetime.strptime(detail['time'], "%H%M").time()

                start = datetime.datetime.combine(detail['date'],startTime,tzinfo=ZoneInfo("Europe/London"))

                eventFreq = detail['freq']



                eventUID = detail.get('uid')

                needsUpdating = detail.get('needsUpdating',False)

                if eventUID is None:
                    detail['uid'] = str(uuid.uuid4())
                    eventUID = detail.get('uid')
                    saveEvents()

                if eventUID in globalUIDs and needsUpdating == False:
                    print('event already in')
                elif eventUID in globalUIDs and needsUpdating:
                    syncUpdates(start,title,eventUID,globalUIDs)
                    detail['needsUpdating'] = False
                else:
                    if detail['syncedPrev'] == False:
                        syncCreate(eventFreq,start,title,eventUID,calendar)
                        detail['needsUpdating'] = False
                        detail['syncedPrev'] = True
                        print("event added")
                    else:
                        print('Event in iCloud deleted, local event deleted to match global')
                        localQueue.append(id)
                localUIDs.add(eventUID)
            for id in localQueue:
                localEvents.pop(id)
            
            for uid in globalUIDs:
                if uid not in localUIDs:
                    comp = globalUIDs[uid].icalendar_component
                    title = str(comp.get('summary',''))
                    start = comp['dtstart'].dt
                    if isinstance(start, datetime.datetime):
                        start = start.astimezone(ZoneInfo("Europe/London"))
                        addEvent(title,start.date(),start.strftime('%H%M'),'',None,uid,True)


                

            saveEvents()
    except AuthorizationError:
        try:
            keyring.delete_password(SERVICE_NAME, email)
        except keyring.errors.PasswordDeleteError:
            pass
        sys.exit('Login failed, check your email and app-specific password')
        





# ARG
def dateArg(text):
    try:
        return parseDate(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{text} is not a valid date, use DDMMYY')
def timeArg(text):
    try:
        return parseTime(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{text} is not a valid time, use HHMM 24 Hours')




    
def viewEvent(eventNum):
    print('Record',eventNum)
    if localEvents[eventNum]['mod']:
        print("Module: ",localEvents[eventNum]['mod'])
    print("Date: ", localEvents[eventNum]['date'].strftime("%d %B %Y"))
    print('Time: ',datetime.datetime.strptime(localEvents[eventNum]['time'],'%H%M').strftime('%H:%M'))  
    print("Description: ",localEvents[eventNum]['desc'])
    print()

def viewAllEvents():
    if not localEvents:
        print('No localEvents created')
        return
    print("--------")
    for eventNum, _ in sorted(localEvents.items(), key=lambda item: item[1]['date']):
        viewEvent(eventNum)
    print("--------")



def buildParser():
    parser = argparse.ArgumentParser(description = 'Manage localEvents and sync them to iCloud calendar. --help for help')
    commands = parser.add_subparsers(dest='command')

    add = commands.add_parser('add', help='Add a new event')
    add.add_argument('desc',help='What the event is')
    add.add_argument('date',type=dateArg,help='Date of event as DDMMYY')
    add.add_argument('time',type=timeArg,help='Time of event as HHMM 24hours')
    add.add_argument('--mod',help='Module (if applicable)',default='')
    add.add_argument('--repeat',help='How often?',choices=['daily','weekly','monthly'])

    commands.add_parser('list', help='Show all localEvents')
    commands.add_parser('upcoming',help='View upcoming localEvents')

    delete = commands.add_parser('delete',help='Delete an event')
    delete.add_argument('id',type=int,help='record number')

    edit = commands.add_parser('edit',help='Edit an event')
    edit.add_argument('id',type=int,help='Record number')
    edit.add_argument('field',choices=['date','time','mod','desc'])
    edit.add_argument('value',help='New value')

    commands.add_parser('sync', help='sync localEvents to iCloud')
    return parser

def runCommand(args):
    if args.command == 'add':
        if args.repeat:
            eventFreq = args.repeat.upper()
        else:
            eventFreq = None
        addEvent(args.desc,args.date,args.time,args.mod,eventFreq,None)
        print('Event added successfully')
    elif args.command == 'edit':
        editEvent(args.id,args.field,args.value)
    elif args.command == 'delete':
        deleteEvent(args.id)
    elif args.command == 'upcoming':
        viewUpcomingEvent()
    elif args.command == 'list':
        viewAllEvents()
    elif args.command == 'sync':
        syncEvents()
    
if __name__ == '__main__':
    parser = buildParser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
    else:
        runCommand(args)