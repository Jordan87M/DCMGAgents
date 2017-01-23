from DCMGClasses.resources import financial

class Plan(object):
    def __init__(self,planner,period):
        self.planner = planner
        self.period = period
        
        self.acceptedBids = []
        self.ownBids = []
    
    def printInfo(self,verbosity = 1):
        print("------------------------------------")
        print("PLAN FROM {pl} for {per}".format(pl = self.planner, per = self.period))
        print("INCLUDES THE FOLLOWING BIDS:")
        for bid in self.acceptedBids:
            bid.printInfo()
        
    def addBid(self,newbid):
        self.acceptedBids.append(newbid)
        if newbid.counterparty == self.planner:
            self.ownBids.append(newbid)
    