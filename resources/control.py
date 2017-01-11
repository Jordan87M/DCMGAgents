class Plan(object):
    def __init__(self,planner,period):
        self.planner = planner
        self.period = period
        
        self.acceptedBids = []
        self.ownBids = []
        self.wholesaleRate = None
        
    def addBid(self,newbid):
        self.acceptedBids.append(newbid)
        if newbid.counterparty == planner.name:
            self.ownBids.append(newbid)
    