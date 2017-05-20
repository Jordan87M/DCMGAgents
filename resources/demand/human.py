class User(object):
    def __init__(self, name):
        self.name = name
        
        self.energyBehaviors = []
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "***HUMAN: {nam}".format(nam = self.name))
        for behavior in self.energyBehaviors:
            behavior.printInfo(depth + 1)
            
    def aggregate(self):
        aggutility = 0
        for behavior in self.energyBehaviors:
            aggutility += behavior.utilityfn
            
        
class EnergyBehavior(object):
    def __init__(self, name, device, utilityfn):
        self.name = name
        
        self.device = device
        self.setpoint = 0
        self.utilityfn = []
        self.params = []
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "ENERGY BEHAVIOR: {name}".format(name = self.name))
        print(tab*depth + "ASSOCIATED DEVICE: ")
        self.device.printInfo(depth + 1)
        
    def setutilityfn(self, fn, params):
        self.utilityfn = fn
        self.params = params
        
    def utilityfunc(self,params):
        self.utilityfn(self)
            
def quadraticbelowthreshold(me,**params):
    if me.setpoint > me.device.state:
        return params.get("weight",1)*(me.setpoint - me.device.state)**2
    else:
        return 0

def quadraticbelowthresholdwcap(me,**params):
    if me.setpoint > me.device.state:
        util = params.get("weight",1)*(me.setpoint - me.device.state)**2
        if util > params.get("cap",9999):
            return cap
        return util
    else:
        return 0
        
def quadratic(me,**params):
    return kwargs.get("weight",1)*(me.setpoint - me.device.state)**2

def constant(me,**params):
    return 


        