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
        

#determine daily rate based on capital cost and rate of return        
def dailyratecalc(capitalCost,discountRate,term):
    dailyrate = (discountRate*(1+discountRate)**(term - 1))*capitalCost
    return dailyrate

def ratecalc(capitalCost,discountRate,term,capacityFactor):
    dailyrate = dailyratecalc(capitalCost,discountRate,term)
    rate = dailyrate/capacityFactor
    return rate