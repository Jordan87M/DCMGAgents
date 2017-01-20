import random

class Bid(object):
    def __init__(self,service,amount,rate,counterparty,period,uid = random.getrandbits(32)):
        self.service = service
        self.amount = amount
        self.rate = rate
        self.counterparty = counterparty
        self.period = period
        self.uid = uid
        
        self.accepted = False
        self.modified = False
    
    def printInfo(self,verbosity = 1):
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
        print("BID INFORMATION for BID {id}".format(id = self.uid))
        print("SERVICE: {service}".format(id = self.service))
        print("AMOUNT: {amt} AT: {rate} Credits/Joule".format(self.amount, self.rate))
        print("FOR PERIOD: {per}".format(per = self.period))
        print("COUNTERPARTY: {ctr}".format(ctr = self.counterparty))
        print("STATUS:\n   ACCEPTED: {acc}    MODIFIED: {mod}".format(acc = self.accepted, mod = self.modified))
        print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")

#determine daily rate based on capital cost and rate of return        
def dailyratecalc(capitalCost,discountRate,term):
    dailyrate = (discountRate*(1+discountRate)**(term - 1))*capitalCost
    return dailyrate

def ratecalc(capitalCost,discountRate,term,capacityFactor):
    dailyrate = dailyratecalc(capitalCost,discountRate,term)
    rate = dailyrate/capacityFactor
    return rate