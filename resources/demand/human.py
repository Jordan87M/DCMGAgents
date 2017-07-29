from twisted.words.protocols.oscar import CAP_CHAT
class User(object):
    def __init__(self, name):
        self.name = name
        
        self.devices = []
        self.energyBehaviors = []
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "***HUMAN: {nam}".format(nam = self.name))
        for behavior in self.energyBehaviors:
            behavior.printInfo(depth + 1)
            
            
    def costFn(self,period,statecomponents):
        #the costFn() method is implemented at the level of the User class
        #to allow the implementation of cost functions that are not independent
        #of other devices
        
        #for now, my cost functions are independent
        totalcost = 0
        for dev in devices:
            devstate = statecomponents[dev.name]
            totalcost += dev.costFn(period.expectedenergycost,devstate)
            
        return totalcost
            
        
class EnergyBehavior(object):
    def __init__(self, name, device, utilityfns):
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
        
    def setcostfn(self, fn, params):
        self.utilityfn = fn
        self.params = params
        
    def costfunc(self,params):
        self.utilityfn(self)
            
class QuadraticCostFn(object):
    def __init__(self,a,b,c):
        self.a = a
        self.b = b
        self.c = c
    
    def eval(self,x):
        return b + a*(x-b)^2
    
class QuadraticWCapCostFn(QuadraticCostFn):
    def __init__(self,a,b,c,cap):
        super(QuadraticWCapCostFn,self).__init__(a,b,c)
        self.cap = cap
        
    def eval(self,x):
        retval = super(QuadraticWCapCostFn,self).eval(x)
        if retval > self.cap:
            return self.cap
        return retval
    
class QuadraticOneSideCostFn(QuadraticCostFn):
    def __init__(self,a,b,c,side):
        super(QuadraticOneSideCostFn,self).__init__(a,b,c)
        self.side = side
        
    def eval(self,x):
        if side == "left":
            if x < self.b:
                return super(QuadraticOneSideCostFn,self).eval(x)
            else:
                return c
        elif side == "right":
            if x > self.b:
                return super(QuadraticOneSideCostFn,self).eval(x)
            else:
                return c
            
class QuadraticOneSideWCapCostFn(QuadraticOneSideWCapCostFn):
    def __init__(self,a,b,c,side,cap):
        super(QuadraticOneSideWCapCostFn,self).__init__(a,b,c,side)
        self.cap = cap
        
    def eval(self,x):
        retval = super(QuadraticOneSideWCapCostFn,self).eval(x)
        if retval > self.cap:
            return self.cap
        return retval
    
class ConstantCostFn(object):
    def __init__(self,c):
        self.c = c
    
    def eval(self,x):
        return self.c
    


        