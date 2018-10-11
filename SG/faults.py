from __future__ import absolute_import
from DCMGClasses.CIP import tagClient

import time

'''
BRANCH_1_BUS_1_FAULT
CROSSTIE_1_FAULT_1
MAIN_BUS_FAULT
'''

#creates a persistent fault
def persistent_fault(tag):
    tagClient.writeTags([tag],[True],"SG")

#creates a fault for a predetermined duration
def timed_fault(tag,duration):
    tagClient.writeTags([tag],[True],"SG")
    time.sleep(duration)
    tagClient.writeTags([tag],[False],"SG")

#reverts any persistent fault states
def cleanup():
    tags = ["BRANCH_1_BUS_1_FAULT","BRANCH_1_BUS_2_FAULT","BRANCH_2_BUS_1_FAULT","BRANCH_2_BUS_2_FAULT",
            "CROSSTIE_1_FAULT_1","CROSSTIE_1_FAULT_2","CROSSTIE_2_FAULT_1","CROSSTIE_2_FAULT_2", "MAIN_BUS_FAULT"]
    vals = [False]*9
    tagClient.writeTags(tags,vals)
    
def shortfaultscen():
    timed_fault("BRANCH_2_BUS_1_FAULT",0.5)
    
def shortfaultscenalt():
    timed_fault("CROSSTIE_1_FAULT_1",0.5)
    
def medfaultscen():
    timed_fault("BRANCH_2_BUS_1_FAULT",1.4)
    
def medfaultscenalt():
    timed_fault("CROSSTIE_1_FAULT_1",1.4)
    
def permfaultscen():
    persistent_fault("BRANCH_2_BUS_1_FAULT")
    
def permfaultscenalt():
    persistent_fault("CROSSTIE_1_FAULT_1")