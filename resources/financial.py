import random

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
        
    def printInfo(self,verbosity = 1):
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print("SUPPLY BID INFORMATION for BID {id}".format(id = self.uid))
        print("SERVICE: {service} FROM: {res}".format(service = self.service, res = self.resourceName))
        print("AMOUNT: {amt} AT: {rate} Credits/Joule".format(amt = self.amount, rate = self.rate))
        print("FOR PERIOD: {per}".format(per = self.period))
        print("COUNTERPARTY: {ctr}".format(ctr = self.counterparty))
        print("STATUS:\n   ACCEPTED: {acc}    MODIFIED: {mod}".format(acc = self.accepted, mod = self.modified))
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")    
        
class DemandBid(BidBase):
    def __init__(self,amount,rate,counterparty,period,uid = None):
        super(DemandBid,self).__init__(amount,rate,counterparty,period,uid)
        #more stuff here later?
        
    def printInfo(self,verbosity = 1):
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print("DEMAND BID INFORMATION for BID {id}".format(id = self.uid))
        print("AMOUNT: {amt} AT: {rate} Credits/Joule".format(amt = self.amount, rate = self.rate))
        print("FOR PERIOD: {per}".format(per = self.period))
        print("COUNTERPARTY: {ctr}".format(ctr = self.counterparty))
        print("STATUS:\n   ACCEPTED: {acc}    MODIFIED: {mod}".format(acc = self.accepted, mod = self.modified))
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")    
    

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
    
