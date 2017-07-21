class DREvent(object):
    def __init__(self,period,specmode,severity,value):
        self.period = period
        self.specmode = specmode
        self.severity = severity
        self.value = value
        
    def costFn(self):
        return -self.value    
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "~DR EVENT~~~")
        print(tab*depth + "PERIOD: {pernum}".format(pernum = period.periodNumber))
        
        
class CurtailmentEvent(DREvent):
    def __init__(self,period,severity,spec,value):
        super(CurtailmentEvent,self).__init__(period,specmode,severity,value)
    
    def printInfo(self,depth):
        tab = "    "
        super(Curtailment,self).printInfo(depth)
        print(tab*depth + "CURTAILMENT LEVEL:")
        print(tab*depth + "  {lev} specified as {spec}".format(lev = self.severity, spec = self.spec))
        print(tab*depth + "ADHERENCE BENEFIT: {val}".format(val = self.value))
        
class LoadUpEvent(DREvent):
    def __init__(self,period,severity,spec,value):
        super(LoadUpEvent,self).__init__(period,specmode,severity,value)
        
    def printInfo(self,depth):
        tab = "    "
        super(Curtailment,self).printInfo(depth)
        print(tab*depth + "LOAD UP INTENSITY:")
        print(tab*depth + "  {lev} specified as {spec}".format(lev = self.severity, spec = self.spec))
        print(tab*depth + "ADHERENCE BENEFIT: {val}".format(val = self.value))
