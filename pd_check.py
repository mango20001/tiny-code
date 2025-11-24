# -*- coding:utf-8 -*-
#-------------------------------------------------------------------------------
# Name:
# Purpose:
#
# Author:      Mark Lee
#
# Created:     12/20/2023 14:39:03
# Copyright:   (c) Mark 2023
# Licence:     <0.0.0>
#-------------------------------------------------------------------------------
#!/usr/bin/env python
# -*- coding:utf-8 -*-
#-------------------------------------------------------------------------------
# Name:        
# Purpose:     
#
# Author:      Mark Lee
#
# Created:     04/28/2023/ 15:55:20
# Copyright:   (c) Mark 2023
# Licence:     <0.0.0>
#-------------------------------------------------------------------------------
#!/usr/bin/env python
import time
from datetime import datetime, date
import json
import re
import requests
from pdconfig import ParamConfig as pc
from db import PgConnect
'''
1. 2022-11-01-T07:00:00 ~ 2023-05-04-T07:00:00 
2. 2022-06-01-T07:00:00 ~ 2022-11-01-T06:59:59

API_URL = ''
PD_TOKEN = ''
TIME_ZONE = 'Asia/Shanghai'
DATE_SINCE = '2023-11-01-T00:00:00'
DATE_UNTIL = '2023-11-30-T23:59:59'
TEAM_ID = 'POX23F2'
FILE_NAME = '2023-11'
'''
class PageDuty:
    def __init__(self):
        # self.session = APISession(pc.PD_TOKEN)
        # self.headers = {
        #     "Content-Type": "application/json",
        #     "Accept": "application/vnd.pagerduty+json;version=2",
        #     "From": "",
        #     "Authorization": "Token token="+pc.PD_TOKEN
        # }
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        self.cookies = {
            '_pagerduty_session' : 'N/A',
        }

    def inc_batch_insert(self, since=None, until=None):
        pgconn = PgConnect()
        if since == None:
            since = pgconn.get_max_created_at()
        
        print(since)

        incidents = self.session.list_all(
            'incidents',  
             params={
                'team_ids[]':[pc.TEAM_ID],
                'time_zone': pc.TIME_ZONE,
                'since':since,
                #'until': until
            }
        )
        print(len(incidents))
        for inc in incidents:
            title = inc["title"] 
            created_at = inc["created_at"]
            status = inc["status"]
            last_status_change_at = inc["last_status_change_at"]
            last_status_change_by = inc["last_status_change_by"]['summary']
            inc_id = inc['id']
            first_trigger_log_entry_id = inc["first_trigger_log_entry"]['id']
            urgency = inc['urgency']  #'urgency': 'high'|'low'
            paged_by_service = inc['service']['summary'] 
            email_body= self.get_firstlog_entry(first_trigger_log_entry_id)
    
            data=(
                inc_id,
                title,
                status,
                created_at,
                urgency,
                paged_by_service,
                last_status_change_at,
                last_status_change_by,
                email_body
            )
            #print(data)
            pgconn.raw_pdinc_insert(data)

        pgconn.close()
            
    def inc_list(self, status, since=None, until=None):
        #status: triggered, acknowledged, resolved
        #print('pd_check/status:'+status)
        result_list = []

        url = f"{pc.INC_URL}/incidents"
        querystring={'statuses[]':status, 
            'time_zone':pc.TIME_ZONE,
            'team_ids[]':[pc.TEAM_ID],
            'since': since,
            'until':until,
            #'since': '2023-12-21-T11:00:00',
            'sort_by': 'created_at:desc'}
    
        incidents = requests.get(url, headers=self.headers, params=querystring, cookies=self.cookies)
        incidents = incidents.json()['incidents']

        for inc in incidents:
            title = inc["title"] 
            created_at = inc["created_at"]
            status = inc["status"] #"resolved" or others
            last_status_change_at = inc["last_status_change_at"]
            last_status_change_by = inc["last_status_change_by"]['summary'] # member name
            inc_id = inc['id']
            first_trigger_log_entry_id = inc["first_trigger_log_entry"]['id'] 
            urgency = inc['urgency']  #'urgency': 'high'|'low'
            paged_by_service = inc['service']['summary']  
            email_body= self.get_firstlog_entry(first_trigger_log_entry_id)
            doc = {
                'inc_id':inc_id,
                'title':title,
                'status':status,
                'created_at':created_at,
                'urgency': urgency,
                'paged_by_service': paged_by_service,
                'last_status_change_at':last_status_change_at,
                'last_status_change_by':last_status_change_by,
                'email_body':email_body
            }
            result_list.append(doc)
        return result_list
    
    def ack_inc(self, inc_id):
        url = f"{pc.INC_URL}/incidents"
        payload = {"incidents": [
                {
                    "id": inc_id,
                    "type": "incident_reference",
                    "status": "acknowledged"
                }
            ]}

        response = requests.request("PUT", url, json=payload, headers=self.headers, cookies=self.cookies)

        return response.text

    def snooze_inc(self, inc_id, duration=None):
        #id = "Q2OMGYUFIDEEJB", duration=86400(s), 24hr
        if not duration:
            duration = 86400 
        print(pc.INC_URL)
        print(inc_id)
        url = f"{pc.INC_URL}/{inc_id}/snooze"
        payload = {"duration": duration}
        response = requests.request("POST", url, json=payload, headers=self.headers, cookies=self.cookies)

        #print(response.text) 
        return response.status_code     

    def get_firstlog_entry(self, first_trigger_log_entry_id):
        url = f"{pc.INC_URL}/log_entries/{first_trigger_log_entry_id}"
        querystring={'include[]':['channels'], 'time_zone':pc.TIME_ZONE}
    
        log_entry = requests.get(url, headers=self.headers, params=querystring, cookies=self.cookies)
    
        # log_entry = self.session.get('/log_entries/'+first_trigger_log_entry_id, 
        #         params={'include[]':['channels'], 'time_zone':pc.TIME_ZONE}
        # )

        try:
            email_body = log_entry.json()['log_entry']['channel']['body']
        except:
            #print(log_entry.json()['log_entry']['html_url'])
            email_body = "None"
        return email_body
    
    def get_timeline(self, inc_id):
        #id = "Q2OMGYUFIDEEJB", duration=7200
        url = pc.INC_URL+inc_id+"/timeline"
        response = requests.request("GET", url, headers=self.headers)

        print(response.text) 

    def get_schedule(self, since, until):
        result = []
        url = f"{pc.INC_URL}/schedules/{pc.SCHEDULE_ID}"
        querystring={
            'time_zone':pc.TIME_ZONE, 
            'since': since, #'2024-01-08-T07:00:00', 
            'until': until
        }
        resp = requests.get(url, headers=self.headers, params=querystring, cookies=self.cookies)
                            
        user_infos = resp.json()['schedule']['final_schedule']["rendered_schedule_entries"]
        for u in user_infos:
            date = u['start']
            day = convert_date_to_day(date)
            tmp_dict = {'name':u['user']['summary'], 'datetime':u['start'], 'day':day}
            #print("{0}, {1}, {2}".format(u['user']['summary'], u['start'], day))
            result.append(tmp_dict)
        
        return result

    @staticmethod
    def filter_prtn(text):
        print('ok')
        pass

def parse_weekend_inc():
    import os
    info = []
    file_list = ['2023-01.json', '2023-02.json', '2023-03.json', '2023-04.json', '2023-05.json', '2023-06.json']

    rootdir = 'N/A'            
    print(os.path.dirname(__file__))                       
    for parent,dirnames,filenames in os.walk(rootdir):    
        for filename in filenames:                        
            with open(os.path.join(parent,filename), 'r') as f:
                for line in f:
                    a = line.strip()
                    b = json.loads(a)
                    timestamp = b['created_at']
                    hr = int(timestamp.split('T')[1].split(':')[0])
                    day = convert_date_to_day(timestamp)
                    '''
                    if day in [6, 7]:
                        if day == 6:
                            t_day = 0
                        else:
                            t_day = 1
                    '''
                    print("[{0}, {1}],".format(day, hr))
                        #print('*****************')
            #break

def convert_date_to_day(date):
    dt = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S+08:00')
    day = dt.weekday()+1
    return day

def parse_prtn(text):
    prtn = re.findall(r'p\d{2,3}', text)
    return prtn

def time_duration():
    s = "2023-02-28T22:00:00+08:00"
    e = "2023-03-02T02:00:00+08:00"
    s_struct = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S+08:00")
    e_struct = datetime.strptime(e, "%Y-%m-%dT%H:%M:%S+08:00")
    seconds = (e_struct - s_struct).total_seconds()
    return seconds

def main():
    pd = PageDuty()
    status = 'acknowledged'
    r = pd.inc_list(status)
    print(r)
    
    since = '2024-04-01-T00:00:00'
    
    """From db: 2024-04-08T10:41:16+08:00 """
    #until = '2024-03-31-T23:59:59'
    #pd.inc_batch_insert()

if __name__ == '__main__':
    main()