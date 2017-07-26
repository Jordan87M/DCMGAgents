from volttron.platform.vip.agent import RPC

class Device(object):
    def __init__(self, initstate):
        self.state = initstate
        
        self.isintermittent = False
        self.issource = False
        self.issink = True
    
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "DEVICE NAME: {name}".format(name = self.name))
    
    
class HeatingElement(Device):
    def __init__(self,**dev):
        super(Heater,self).__init__(**dev)
        self.shc = dev["specificheatcapacity"]
        self.mass = dev["mass"]        
        self.thermR = dev["thermalresistance"]
        self.maxSetpoint = dev["maxsetpoint"]
        self.deadband = dev["deadband"]
        self.deltat = dev["deltat"]
        
        self.tamb = self.vip.rpc.call('weatheragent','getTemperatureRPC').get(timeout = 4)
        self.setpoint = self.tamb 
        
        self.gridpoints = [25,30,35,40]
        self.actionpoints = [0,1]
        
        self.elementOn = False
        self.temperature = self.tamb
    
    def getPowerFromPU(self,pu):
        return pu*self.maxSetpoint
    
    def getPUFromPower(self,power):
        return power/self.maxSetpoint
    
    def updateSetpoint(self,new):
        if new > self.maxSetpoint:
            new = self.maxSetpoint
            
        self.setpoint = new
        
    def applySimulatedInput(self,state,input,duration):
        pass
        
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
                
        self.temperature = (pin-(self.state - self.tamb)/self.thermR)/(self.mass*self.shc)*self.deltat + self.temperature
    
    def inputCostFn(self,puaction,energycost,duration):
        power = self.getPowerFromPU(puaction)
        return power*duration*energycost    
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print(tab*depth + "DEVICE SUMMARY FOR HEATER: {heat}".format(heat = self.name))
        print(tab*depth + "OWNER: {own}".format(own = self.owner))
        print(tab*depth + "SETPOINT: {stp}    CURRENT: {temp}".format(stp = self.tempSetpoint, temp = objectTemp ))
        print(tab*depth + "HEATER POWER: {pow}".format(pow = self.heaterPower))
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
    
class HeatEngine(Device):
    pass