from DCMGClasses.resources import financial

class Plan(object):
    def __init__(self,planner,period):
        self.planner = planner
        self.period = period
        
        self.acceptedBids = []
        self.ownBids = []
        self.wholesaleRate = None
    
    def printInfo(self,verbosity = 1):
        print("------------------------------------")
        print("PLAN FROM {pl} for {per}".format(pl = self.planner, per = self.period))
        print("WHOLESALE PRICE THIS PERIOD: {price}".format(price = self.wholesaleRate))
        print("INCLUDES THE FOLLOWING BIDS:")
        for bid in self.acceptedBids:
            bid.printInfo()
        
    def addBid(self,newbid):
        self.acceptedBids.append(newbid)
        if newbid.counterparty == planner.name:
            self.ownBids.append(newbid)
    