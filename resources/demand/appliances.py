from volttron.platform.vip.agent import RPC

class Device(object):
    def __init__(self, **dev):
        self.name = dev["name"]
        self.owner = dev["owner"]
        
        self.isintermittent = False
        self.issource = False
        self.issink = True
        
        self.associatedbehavior = None
    
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "DEVICE NAME: {name}".format(name = self.name))
        
    def costFn(self,period,devstate):
        return self.associatedbehavior.costFn(period,devstate)
    
    
class HeatingElement(Device):
    def __init__(self,**dev):
        super(HeatingElement,self).__init__(**dev)
        self.shc = dev["specificheatcapacity"]
        self.mass = dev["mass"]        
        self.thermR = dev["thermalresistance"]
        self.maxSetpoint = dev["maxsetpoint"]
        self.deadband = dev["deadband"]
        self.deltat = dev["deltat"]
        self.nominalpower = dev["nominalpower"]
        
        self.tamb = 25
        self.setpoint = self.tamb 
        
        self.gridpoints = [25,30,35,40,45]
        self.actionpoints = [0,1]
        
        self.elementOn = False
        self.temperature = self.tamb
    
    def getPowerFromPU(self,pu):
        return pu*self.nominalpower
    
    def getPUFromPower(self,power):
        return power/self.nominalpower
    
    def updateSetpoint(self,new):
        if new > self.maxSetpoint:
            new = self.maxSetpoint
            
        self.setpoint = new
        
    #Euler's method, use only for relatively short time periods
    def applySimulatedInput(self,state,input,duration):
        et = 0
        defstep = 5
        if input != 0:
            input = 1
        while et < duration:
            if (duration - et) >= defstep:
                step = defstep
            else:
                step = (duration -et)
            et += step
            state = (((self.nominalpower*input)-((state - self.tamb)/self.thermR))/(self.mass*self.shc))*step + state
            #print("another step: after {et} seconds out of {dur} newstate is {ns}".format(et = et, dur = duration, ns = state))
        return state
        
    def simulationStep(self,deltat,pin):
        if self.elementOn:
            if self.temperature > self.setpoint + self.deadband/2:
                #turn element off
                self.elementOn = False
                pin = 0
        else:
            if self.temperature < self.setpoint - self.deadband/2:
                #turn element on
                self.elementOn = True
                
        self.temperature = ((pin-(self.state - self.tamb)/self.thermR)/(self.mass*self.shc))*self.deltat + self.temperature
        return self.elementOn
    
    def inputCostFn(self,puaction,period,state,duration):
        power = self.getPowerFromPU(puaction)
        #print("temporary debug: cost: {cost}, power: {pow}, duration: {dur}".format(cost = period.expectedenergycost, pow = power, dur = duration))
        return power*duration*period.expectedenergycost    
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print(tab*depth + "DEVICE SUMMARY FOR HEATER: {heat}".format(heat = self.name))
        print(tab*depth + "OWNER: {own}".format(own = self.owner))
        print(tab*depth + "SETPOINT: {stp}    CURRENT: {temp}".format(stp = self.setpoint, temp = self.temperature ))
        print(tab*depth + "STATE: {state}".format(state = self.elementOn))
        if self.associatedbehavior:
            print(tab*depth + "BEHAVIOR:")
            self.associatedbehavior.printInfo(depth + 1)
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
    
class HeatPump(Device):
    def __init__(self,**dev):
        super(HeatPump,self).__init__(**dev)
        self.vol = dev["volume"]
        self.heatcap = self.vol*1.2*1007  #volume * approx. density * specific heat capacity
        self.thermR = dev["thermalresistance"]
        self.maxSetpoint = dev["minsetpoint"]
        self.deadband = dev["deadband"]
        self.deltat = dev["deltat"]
        self.nominalpower = dev["nominalpower"]
        self.carnotrelativeefficiency = dev["relativeefficiency"]
        
        self.tamb = 25
        self.setpoint = self.tamb 
        
        self.gridpoints = [15,20,25,30,35,40]
        self.actionpoints = [0,1]
        
        self.on = False
        self.temperature = self.tamb
    
    def getPowerFromPU(self,pu):
        return pu*self.nominalpower
    
    def getPUFromPower(self,power):
        return power/self.nominalpower
    
    def updateSetpoint(self,new):
        if new > self.maxSetpoint:
            new = self.maxSetpoint
            
        self.setpoint = new
        
    #Euler's method, use only for relatively short time periods
    def applySimulatedInput(self,state,input,duration,pin = "default"):
        if pin == "default":
            pin = self.nominalpower
        et = 0
        defstep = 5
        if input != 0:
            input = 1
        while et < duration:
            if (duration - et) >= defstep:
                step = defstep
            else:
                step = (duration - et)
            et += step
            #estimate working fluid temperatures
            tc = state - 6
            th = self.tamb + 4
            efficiency = self.carnotrelativeefficiency*(1-((tc + 273)/(th + 273)))
            peff = pin * efficiency
            state = ((peff-((state - self.tamb)/self.thermR))/(self.heatcap))*step + state            
            print("another step: after {et} seconds out of {dur} newstate is {ns}".format(et = et, dur = duration, ns = state))
        return state
        
    def simulationStep(self,deltat,pin):
        if self.on:
            if self.temperature > self.setpoint + self.deadband/2:
                #turn element off
                self.on = False
                pin = 0
        else:
            if self.temperature < self.setpoint - self.deadband/2:
                #turn element on
                self.on = True
        if self.on:
            input = 1
        else:
            input = 0
        self.temperature = self.applySimulatedInput(self.temperature,input,deltat,pin)
        return self.on
    
    def inputCostFn(self,puaction,period,state,duration):
        power = self.getPowerFromPU(puaction)
        print("temporary debug: cost: {cost}, power: {pow}, duration: {dur}".format(cost = period.expectedenergycost, pow = power, dur = duration))
        return power*duration*period.expectedenergycost    
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print(tab*depth + "DEVICE SUMMARY FOR HEATER: {heat}".format(heat = self.name))
        print(tab*depth + "OWNER: {own}".format(own = self.owner))
        print(tab*depth + "SETPOINT: {stp}    CURRENT: {temp}".format(stp = self.setpoint, temp = self.temperature ))
        print(tab*depth + "STATE: {state}".format(state = self.on))
        if self.associatedbehavior:
            print(tab*depth + "BEHAVIOR:")
            self.associatedbehavior.printInfo(depth + 1)
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        
class Refrigerator(HeatPump):
    def __init__(self,**dev):
        super(Refrigerator,self).__init__(**dev)
        self.gridpoints = [0,2,4,6,8]
        
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print(tab*depth + "DEVICE SUMMARY FOR REFRIGERATOR: {me}".format(me = self.name))
        print(tab*depth + "OWNER: {own}".format(own = self.owner))
        print(tab*depth + "SETPOINT: {stp}    CURRENT: {temp}".format(stp = self.setpoint, temp = self.temperature ))
        print(tab*depth + "STATE: {state}".format(state = self.on))
        if self.associatedbehavior:
            print(tab*depth + "BEHAVIOR:")
            self.associatedbehavior.printInfo(depth + 1)
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
    