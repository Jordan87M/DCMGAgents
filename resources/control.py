from DCMGClasses.resources import groups, optimization
from DCMGClasses.resources import misc
from datetime import datetime, timedelta

import random

#this class represents the set of planning periods within the time horizon of the home agent.
#agents won't consider what will happen after the last planning period in the current window
#when planning their course of action
#params
#-length: number of planning periods in window
#-startingPeriod: period number of the first period in the new window
#-startTime: datetime object giving start time of first period
#-increment: default number of seconds between planning periods
class Window(object):
    def __init__(self,planner,length,startingPeriod,startTime,increment):
        self.windowlength = length
        self.periods = []
        self.nextstarttime = startTime
        self.increment = increment
        self.planner = planner
        
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
        endtime = self.nextstarttime + timedelta(seconds = self.increment)
        newperiod = Period(self.nextperiodnumber,self.nextstarttime,endtime)
        newperiod.planner = self.planner
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
        for period in self.periods:
            if period.periodNumber == number:
                return period
        return None
                
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "PLANNING WINDOW for periods {start} to {end}".format(start = self.periods[0].periodNumber, end = self.periods[-1].periodNumber))
        print(tab*depth + ">>PERIODS:")
        for period in self.periods:
            print(tab*depth + ">PERIOD:")
            period.printInfo(depth + 1)
        
class Period(object):
    def __init__(self,periodNumber,startTime,endTime):
        self.periodNumber = periodNumber
        self.startTime = startTime
        self.endTime = endTime
        self.planner = None
        
        self.pendingdrevents = []
        self.accepteddrevents = []
        self.forecast = []
        
        self.expectedenergycost = 0
        
        #initialize the plan for this period
        self.plan = Plan(self,self.planner)
        
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
        tab = "    "
        print(tab*depth + "SUMMARY OF PERIOD {num}".format(num = self.periodNumber))
        print(tab*depth + "START: {start}".format(start = self.startTime.isoformat()))
        print(tab*depth + "END: {end}".format(end = self.endTime))
        print(tab*depth + "PLAN INFORMATION:")
        self.plan.printInfo(depth + 1)
        
    
class Plan(object):
    def __init__(self,period,planner):
        self.period = period
        self.planner = planner
        
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
        
    def makeGrid(self,period,gridstates,costfunc):
        self.stategrid = optimization.StateGrid(period,gridstates,costfunc)
        
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
        
    def printInfo(self, depth = 0):
        tab = "    "
        print(tab*depth + "PLAN for {per}".format(per = self.period.periodNumber))
        print(tab*depth + "INCLUDES THE FOLLOWING BIDS ({n} bids for {ts} W):".format(n = len(self.acceptedBids), ts = self.totalsupply))
        for bid in self.acceptedBids:
            bid.printInfo(depth + 1)
        print(tab*depth + "INCLUDES THE FOLLOWING RESERVE BIDS ({n} bids for {tr} W):".format(n = len(self.reserveBids), tr = self.totalreserve))
        for bid in self.reserveBids:
            bid.printInfo(depth + 1)
        print(tab*depth + "ANTICIPATED CONSUMPTION ({n} bids for {td} W):".format(n = len(self.plannedConsumption), td = self.totaldemand))
        for bid in self.plannedConsumption:
            bid.printInfo(depth + 1)
        print(tab*depth + "OPTIMAL CONTROL:")
        if self.optimalcontrol:
            self.optimalcontrol.printInfo(depth + 1)
        
            
class Forecast(object):
    def __init__(self,data,period):
        self.data = data
        self.creationperiod = period
            
#financial stuff
class BidBase(object):
    def __init__(self,amount,rate,counterparty,period,uid = None):
        self.amount = amount
        self.rate = rate
        self.counterparty = counterparty
        self.period = period
                
        self.accepted = False
        self.modified = False
        
        #if we are creating this bid to correspond to a preexisting bid, we can specify the uid
        #otherwise, generate an id randomly
        if uid is None:
            self.uid = random.getrandbits(32)
        else:
            self.uid = uid
    

class SupplyBid(BidBase):
    def __init__(self,resourceName,service,amount,rate,counterparty,period,uid = None):
        super(SupplyBid,self).__init__(amount,rate,counterparty,period,uid)
        self.service = service
        self.resourceName = resourceName
        
    def printInfo(self, depth = 0, verbosity = 1):
        spaces = '  '
        print(spaces*depth + "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print(spaces*depth + "SUPPLY BID INFORMATION for BID {id}".format(id = self.uid))
        print(spaces*depth + "SERVICE: {service} FROM: {res}".format(service = self.service, res = self.resourceName))
        print(spaces*depth + "AMOUNT: {amt} AT: {rate} Credits/Joule".format(amt = self.amount, rate = self.rate))
        print(spaces*depth + "FOR PERIOD: {per}".format(per = self.period))
        print(spaces*depth + "COUNTERPARTY: {ctr}".format(ctr = self.counterparty))
        print(spaces*depth + "STATUS:\n   ACCEPTED: {acc}    MODIFIED: {mod}".format(acc = self.accepted, mod = self.modified))
        print(spaces*depth + "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")    
        
class DemandBid(BidBase):
    def __init__(self,amount,rate,counterparty,period,uid = None):
        super(DemandBid,self).__init__(amount,rate,counterparty,period,uid)
        #more stuff here later?
        
    def printInfo(self, depth = 0):
        spaces = "    "
        print(spaces*depth + "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print(spaces*depth + "DEMAND BID INFORMATION for BID {id}".format(id = self.uid))
        print(spaces*depth + "AMOUNT: {amt} AT: {rate} Credits/Joule".format(amt = self.amount, rate = self.rate))
        print(spaces*depth + "FOR PERIOD: {per}".format(per = self.period))
        print(spaces*depth + "COUNTERPARTY: {ctr}".format(ctr = self.counterparty))
        print(spaces*depth + "STATUS:\n   ACCEPTED: {acc}    MODIFIED: {mod}".format(acc = self.accepted, mod = self.modified))
        print(spaces*depth + "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")    
    

#determine daily rate based on capital cost and rate of return        
def dailyratecalc(capitalCost,discountRate,term):
    yearlyrate = ((discountRate*(1+discountRate)**(term - 1))*capitalCost)/(((1+discountRate)**term)-1)
    dailyrate = yearlyrate/365   #close enough
    return dailyrate

def ratecalc(capitalCost,discountRate,term,capacityFactor):
    dailyrate = dailyratecalc(capitalCost,discountRate,term)
    rate = dailyrate/capacityFactor
    return rate

def acceptbidasis(bid):
    bid.accepted = True
    bid.modified = False
    
def acceptbidmod(bid,modamount):
    bid.accepted = True
    bid.modified = True
    bid.amount = bid.amount - modamount
    
def rejectbid(bid):
    bid.accepted = False
    bid.modified = False
    