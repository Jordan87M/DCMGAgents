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
        
        self.gridpoints = [25,30,35,40]
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
        if input != 0:
            input = 1
        newstate = (((self.nominalpower*input)-(state - self.tamb)/self.thermR)/(self.mass*self.shc))*duration + state
        return newstate
        
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
        print("temporary debug: cost: {cost}, power: {pow}, duration: {dur}".format(cost = period.expectedenergycost, pow = power, dur = duration))
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
    
class HeatEngine(Device):
    pass