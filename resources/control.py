from DCMGClasses.resources import financial, groups, optimization
from DCMGClasses.resources import misc
from datetime import datetime, timedelta

#this class represents the set of planning periods within the time horizon of the home agent.
#agents won't consider what will happen after the last planning period in the current window
#when planning their course of action
#params
#-length: number of planning periods in window
#-startingPeriod: period number of the first period in the new window
#-startTime: datetime object giving start time of first period
#-increment: default number of seconds between planning periods
class Window(object):
    def __init__(self,length,startingPeriod,startTime,increment):
        self.windowlength = length
        self.periods = []
        self.nextstarttime = startTime
        self.increment = increment
        
        self.nextperiodnumber = startingPeriod
        for i in range(self.windowlength):
            self.appendPeriod()
    
    #remove the expired period and add a new one to the end of the list
    def shiftWindow(self):
        #get rid of oldest period
        self.periods.pop(0)
        #remove link to newly removed period
        self.periods[0].previousperiod = None
        
        self.appendPeriod()
        
    #create a new Period instance and append it to the list of periods in the window
    def appendPeriod(self):
        endtime = self.nextstarttime + timedelta(seconds = increment)
        newperiod = Period(self.nextperiodnumber,self.nextstarttime,endtime)
        #default assumption is that price won't change from previous period
        if self.periods:
            newperiod.setExpectedCost(self.periods[-1].expectedenergycost)
            #link new period to last one currently in list
            newperiod.previousperiod = self.periods[-1]
            #link last period to new period
            self.periods[-1].nextperiod = newperiod
        self.periods.append(newperiod)
        self.nextperiodnumber += 1
        self.nextstarttime = endtime
        
    
    def rescheduleWithNewInterval(self,periodnumber,newstarttime,newinterval):
        self.increment = newinterval
        self.rescheduleSubsequent(periodnumber,newstarttime)
            
    def rescheduleSubsequent(self,periodnumber,newstarttime):
        for period in periods:
            if period.periodnumber >= periodnumber:
                period.startTime = newstarttime
                endtime = newstarttime + timdelta(seconds = self.increment)
                period.endTime = endtime
                newstarttime = endtime
                self.nextstarttime = newstarttime
                
    def getPeriodByNumber(self,number):
        for period in periods:
            if period.periodNumber == number:
                return period
                
        

class Period(object):
    def __init__(self,periodNumber,startTime,endTime):
        self.periodNumber = periodNumber
        self.startTime = startTime
        self.endTime = endTime
        
        self.pendingdrevents = []
        self.accepteddrevents = []
        self.forecast = []
        
        self.expectedenergycost = 0
        
        #initialize the plan for this period
        self.plan = Plan(periodNumber)
        
        #links to previous and subsequent periods
        self.previousperiod = None
        self.nextperiod = None
        
    def setExpectedCost(self,cost):
        self.expectedenergycost = cost
        
    def newDRevent(self,event):
        self.pendingdrevents.append(event)
        
    def acceptDRevent(self,event):
        self.accepteddrevents.append(event)
        self.pendingdrevents.remove(event)
    
    def addForecast(self,forecast):
        self.forecast.append(forecast)
        
    def printInfo(self, depth = 0):
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print("SUMMARY OF PERIOD {num}".format(num = self.periodNumber))
        print("START: {start}".format(start = self.startTime.isoformat()))
        print("END: {end}".format(end = self.endTime))
        if self.action is not None:
            self.action.printInfo(depth + 1)
        else:
            print("no plan yet")
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
    
class Plan(object):
    def __init__(self,periodNumber):
        self.periodNumber = periodNumber
        
        self.acceptedBids = []
        self.reserveBids = []
        self.ownBids = []
        self.plannedConsumption = []
        
        
        self.totalsupply = 0
        self.totalreserve = 0
        self.totaldemand = 0
        
        self.stategrid = None
        self.admissiblecontrols = None
        self.optimalcontrol = None
        
    def addGrid(self,grid):
        self.stategrid = grid
        
    def setAdmissibleInputs(self,inputs):
        temp = self.admissiblecontrols
        self.admissiblecontrols = inputs
        return temp
    
    def addBid(self,newbid):
        for bid in self.acceptedBids:
            if bid.uid == newbid.uid:
                print("can't add duplicate bid ({id}) to period {per} plan".format(id = newbid.uid, per = self.period))
                return
        for bid in self.reserveBids:
            if bid.uid == newbid.uid:
                print("can't add duplicate reserve bid ({id}) to period {per} plan".format(id = newbid.uid, per = self.period))
                return
        
        if newbid.service == "reserve":
            self.reserveBids.append(newbid)
            self.totalreserve += newbid.amount
        elif newbid.service == "power":
            self.acceptedBids.append(newbid)            
            self.totalsupply += newbid.amount
        
        if newbid.counterparty == self.planner:
            self.ownBids.append(newbid)
            
    def removeBid(self,bid):
        self.acceptedBids.remove(bid)
        self.totalsupply -= bid.amount
        if bid.counterparty == self.planner:
            self.ownBids.remove(bid)            
            
    def addConsumption(self,demandbid):
        self.plannedConsumption.append(demandbid)
        self.totaldemand += demandbid.amount
        
    def removeConsumption(self,demandbid):
        self.plannedConsumption.remove(demandbid)
        self.totaldemand -= demandbid.amount
        
    def printInfo(self, depth = 0, verbosity = 1):
        print("------------------------------------")
        print("PLAN for {per}".format(per = self.period))
        print("INCLUDES THE FOLLOWING BIDS ({n} bids for {ts} W):".format(n = len(self.acceptedBids), ts = self.totalsupply))
        for bid in self.acceptedBids:
            bid.printInfo(depth + 1)
        print("INCLUDES THE FOLLOWING RESERVE BIDS ({n} bids for {tr} W):".format(n = len(self.reserveBids), tr = self.totalreserve))
        for bid in self.reserveBids:
            bid.printInfo(depth + 1)
        print("ANTICIPATED CONSUMPTION ({n} bids for {td} W):".format(n = len(self.plannedConsumption), td = self.totaldemand))
        for bid in self.plannedConsumption:
            bid.printInfo(depth + 1)
        print("------------------------------------")
            
class Forecast(object):
    def __init__(self,data,period):
        self.data = data
        self.creationperiod = period
            
