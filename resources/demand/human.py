

#from twisted.words.protocols.oscar import CAP_CHAT
# class User(object):
#     def __init__(self, name):
#         self.name = name
#         
#         self.devices = []
#         self.energyBehaviors = []
#         
#     def printInfo(self,depth):
#         tab = "    "
#         print(tab*depth + "***HUMAN: {nam}".format(nam = self.name))
#         for behavior in self.energyBehaviors:
#             behavior.printInfo(depth + 1)
#             
#             
#     def costFn(self,period,statecomps):
#         #the costFn() method is implemented at the level of the User class
#         #to allow the implementation of cost functions that are not independent
#         #of other devices
#         
#         #for now, my cost functions are independent
#         totalcost = 0
#         for devkey in statecomps:
#             device = listparse.lookUpByName(devkey, self.Devices)
#             totalcost += dev.costFn(period.expectedenergycost,statecomps[dev.name])
#             
#         return totalcost
            
        
class EnergyBehavior(object):
    def __init__(self, name, device, utilityfn = None):
        self.name = name
        
        self.device = device
        self.setpoint = 0
        self.params = []
        
        if utilityfn:
            self.utilityfn = utilityfn
        
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "ENERGY BEHAVIOR: {name}".format(name = self.name))
        self.utilityfn.printInfo(depth + 1)
        
        
    def setcostfn(self, fn, params):
        self.utilityfn = fn
        self.params = params
        
    def costFn(self,period,devstate):
        #period not currently in use
        return self.utilityfn.eval(devstate)
            
class QuadraticCostFn(object):
    def __init__(self,a,b,c):
        self.a = a
        self.b = b
        self.c = c
    
    def eval(self,x):
        return self.b + self.a*(x-self.c)**2
    
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "COST FUNCTION = {b} + {a}*(x-{c})**2".format(a = self.a,b = self.b,c = self.c))
    
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
                return self.c
        elif side == "right":
            if x > self.b:
                return super(QuadraticOneSideCostFn,self).eval(x)
            else:
                return self.c
            
class QuadraticOneSideWCapCostFn(QuadraticOneSideCostFn):
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
    


        