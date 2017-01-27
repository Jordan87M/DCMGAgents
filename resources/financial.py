import random

class Bid(object):
    def __init__(self,resourceName,service,amount,rate,counterparty,period,uid = None):
        self.service = service
        self.amount = amount
        self.rate = rate
        self.counterparty = counterparty
        self.period = period
        self.resourceName = resourceName
                
        self.accepted = False
        self.modified = False
        
        #if we are creating this bid to correspond to a preexisting bid, we can specify the uid
        #otherwise, generate an id randomly
        if uid is None:
            self.uid = random.getrandbits(32)
        else:
            self.uid = uid
    
    def printInfo(self,verbosity = 1):
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print("BID INFORMATION for BID {id}".format(id = self.uid))
        print("SERVICE: {service} FROM: {res}".format(service = self.service, res = self.resourceName))
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