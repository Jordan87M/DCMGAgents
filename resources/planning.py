class PlanningWindow(object):
    def __init__(self,length):
        self.length = length
        
        self.plans = []
        
        for i in range(length):
            self.plans.append(Plans(i))

    def advancePeriod(self):
        self.plans.remove(plans[0])
        self.plans.add(Plan(plans[-1].periodNumber + 1))
    
    
    
class Plan(object):
    def __init__(self,periodNumber):
        self.periodNumber = periodNumber
        
        self.DRloadupavail = False
        self.DRcurtailavail = False
    
    