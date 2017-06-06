from DCMGClasses.resources import financial, groups
from DCMGClasses.resources import misc

class Plan(object):
    def __init__(self,period,planner):
        self.planner = planner
        self.period = period
        
        self.acceptedBids = []
        self.reserveBids = []
        self.ownBids = []
        self.plannedConsumption = []
        
        self.totalsupply = 0
        self.totalreserve = 0
        self.totaldemand = 0
    
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
    
class Period(object):
    def __init__(self,periodNumber,startTime,endTime,planner):
        self.periodNumber = periodNumber
        self.startTime = startTime
        self.endTime = endTime
        
        #initialize the plan for this period
        self.actionPlan = Plan(self.periodNumber,planner)
        
    def printInfo(self, depth = 0):
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print("SUMMARY OF PERIOD {num}".format(num = self.periodNumber))
        print("START: {start}".format(start = self.startTime.isoformat()))
        print("END: {end}".format(end = self.endTime))
        if self.actionPlan is not None:
            self.actionPlan.printInfo(depth + 1)
        else:
            print("no plan yet")
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")