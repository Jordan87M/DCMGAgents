

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
        
        return self.utilityfn.eval(devstate)
            
class QuadraticCostFn(object):
    def __init__(self,**params):
        self.a = params["a"]
        self.b = params["b"]
        self.c = params["c"]
        
        self.name = "quad"
    
    def eval(self,x):
        return self.b + self.a*(x-self.c)**2
    
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "COST FUNCTION = {b} + {a}*(x-{c})**2".format(a = self.a,b = self.b,c = self.c))
    
class QuadraticWCapCostFn(QuadraticCostFn):
    def __init__(self,**params):
        super(QuadraticWCapCostFn,self).__init__(**params)
        self.cap = params["cap"]
        
        self.name = "quadcap"
        
    def eval(self,x):
        retval = super(QuadraticWCapCostFn,self).eval(x)
        if retval > self.cap:
            return self.cap
        return retval
    
class QuadraticOneSideCostFn(QuadraticCostFn):
    def __init__(self,**params):
        super(QuadraticOneSideCostFn,self).__init__(**params)
        self.side = params["side"]
        
        self.name = "quadmono"
        
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
    def __init__(self,**params):
        super(QuadraticOneSideWCapCostFn,self).__init__(**params)
        self.cap = params["cap"]
        
        self.name = "quadmonocap"
        
    def eval(self,x):
        retval = super(QuadraticOneSideWCapCostFn,self).eval(x)
        if retval > self.cap:
            return self.cap
        return retval
    
class ConstantCostFn(object):
    def __init__(self,**params):
        self.c = params["c"]
        
        self.name = "const"
    
    def eval(self,x):
        return self.c
    
class PiecewiseConstant(object):
    def __init__(self,**params):
        self.values = params["values"]
        self.bounds = params["bounds"]
        self.bounds.sort()
        
        self.name = "piecewise"
        
    def eval(self,x):
        for index,bound in enumerate(self.bounds):
            if x <= bound:
                return self.values[index]
        return self.values[-1]
    
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "PIECEWISE CONSTANT with {n} intervals".format(n = len(self.values)))
    
    
class Interpolated(object):
    def __init__(self,**params):
        self.states = params["states"]
        self.values = params["values"]
        
        self.name = "interpolate"
        
    def eval(self,z):
        rindex = None
        for index,state in enumerate(self.states):
            if z <= state:
                rindex = index
                break
        if not rindex:
            return self.values[-1]
        if rindex == 0:
            return self.values[0]
        
        x1 = self.states[rindex-1]
        y1 = self.values[rindex-1]
        x2 = self.states[rindex]
        y2 = self.values[rindex]
        
        out = (((y2-y1)/(x2-x1))*(z - x1)) + y1
        return out
          

        