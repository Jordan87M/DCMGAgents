from DCMGClasses.resources import financial, groups
from DCMGClasses.resources import misc

class Plan(object):
    def __init__(self,period,planner):
        self.planner = planner
        self.period = period
        
        self.acceptedBids = []
        self.ownBids = []
    
    def printInfo(self,verbosity = 1):
        print("------------------------------------")
        print("PLAN for {per}".format(per = self.period))
        print("INCLUDES THE FOLLOWING BIDS ({n}):".format(n = len(self.acceptedBids)))
        for bid in self.acceptedBids:
            bid.printInfo()
        print("------------------------------------")
        
    def addBid(self,newbid):
        self.acceptedBids.append(newbid)
        if newbid.counterparty == self.planner:
            self.ownBids.append(newbid)
    
class Period(object):
    def __init__(self,periodNumber,startTime,endTime,planner):
        self.periodNumber = periodNumber
        self.startTime = startTime
        self.endTime = endTime
        
        #initialize the plan for this period
        self.actionPlan = Plan(self.periodNumber,planner)
        
    def printInfo(self):
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print("SUMMARY OF PERIOD {num}".format(num = self.periodNumber))
        print("START: {start}".format(start = self.startTime.isoformat()))
        print("END: {end}".format(end = self.endTime))
        if self.actionPlan is not None:
            self.actionPlan.printInfo()
        else:
            print("no plan yet")
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")