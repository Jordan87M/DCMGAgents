from volttron.platform.vip.agent import RPC

class Device(object):
    def __init__(self, **dev):
        self.name = dev["name"]
        self.owner = dev["owner"]
        self.nominalpower = dev["nominalpower"]
        
        self.isintermittent = False
        self.issource = False
        self.issink = True
        
        self.associatedbehavior = None
        
        self.snapstate = []
        self.gridpoints = []
        self.actionpoints = []
        self.tempgridpoints = []
        
    def stateEngToPU(self,eng):
        return eng/self.statebase
    
    def statePUToEng(self,pu):
        return pu*self.statebase
        
    def addCurrentStateToGrid(self):
        #obtain current state
        currentstate = self.getState()
        #print("DEVICE {me} adding state {cur} to grid".format(me = self.name, cur = currentstate))
        #if the device has a state
        if currentstate:
            #and it isn't already in the list of grids
            #print("has a state")
            if currentstate not in self.gridpoints and currentstate not in self.snapstate:
                #record the added state
                self.snapstate.append(currentstate)
                if currentstate not in self.tempgridpoints:
                    self.tempgridpoints.append(currentstate)
                #print("not already in state. added : {pts}".format(pts = self.gridpoints))
        return currentstate
                
    def revertStateGrid(self):
        for point in self.tempgridpoints:
            if point in self.snapstate:
                #print("removing point {pt} from grid".format(pt = point))
                self.snapstate.remove(point)
            self.tempgridpoints.remove(point)
        
    def getState(self):
        return None
    
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
        
        self.tamb = 25
        self.statebase = 50.0
        self.setpoint = dev["initsetpoint"]
        
        self.gridpoints = [0.5, 0.6, 0.7, 0.8, 0.9]
        self.actionpoints = [0,1]
        
        self.elementOn = False
        self.temperature = dev["inittemp"]
        
    def getState(self):
        return self.stateEngToPU(self.temperature)
    
    def getPowerFromPU(self,pu):
        return pu*self.nominalpower
    
    def getPUFromPower(self,power):
        return power/self.nominalpower
    
    def updateSetpoint(self,new):
        if new > self.maxSetpoint:
            new = self.maxSetpoint
            
        self.setpoint = new
        
    def getActionpoints(self,mode = "hifi"):
        return self.actionpoints
        
    def getGridpoints(self,mode = "hifi"):
        if mode == "hifi":
            grid = self.gridpoints[:]
            grid.extend(self.snapstate)
            return grid
        elif mode == "lofi":
            grid = [ 0.5, 0.75, 0.9]
            grid.extend(self.snapstate)
            return grid
        elif mode == "dyn":
            dynamicgrid = []
            dynamicgrid.extend(self.snapstate)
            initstate = self.getState()            
            newstate = self.applySimulatedInput(initstate,1,30)
            if newstate <= 1 and newstate >= 0: 
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(newstate,1,60)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(initstate,0,30)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(newstate,0,60)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
        
            print("generated gridpoints dynamically for {dev}: {grd}".format(dev = self.name, grd = dynamicgrid))
            return dynamicgrid
        
    #Euler's method, use only for relatively short time periods
    def applySimulatedInput(self,state,input,duration,pin = "default"):
        state = self.statePUToEng(state)
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
                step = (duration -et)
            et += step
            state = (((pin*input)-((state - self.tamb)/self.thermR))/(self.mass*self.shc))*step + state
            #print("another step: after {et} seconds out of {dur} newstate is {ns}".format(et = et, dur = duration, ns = state))
            
        return self.stateEngToPU(state)
        
    def simulationStep(self,pin,duration):
        if pin > 0.0005:
            input = 1
            self.elementOn = True
        else:
            input = 0
            self.elementOn = False
        
        self.temperature = self.applySimulatedInput(self.temperature,input,duration,pin)
        self.printInfo()
        return self.temperature
    
    def inputCostFn(self,puaction,period,state,duration):
        power = self.getPowerFromPU(puaction)
        #print("temporary debug: cost: {cost}, power: {pow}, duration: {dur}".format(cost = period.expectedenergycost, pow = power, dur = duration))
        return power*duration*period.expectedenergycost    
        
    def printInfo(self,depth = 0):
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
        self.carnotrelativeefficiency = dev["relativeefficiency"]
        
        self.tamb = 25
        self.tbase = 40
        self.setpoint = dev["initsetpoint"]
        
        self.gridpoints = [0.375, 0.5, 0.625, 0.75, 0.875, 1]
        self.actionpoints = [0,1]
        
        self.on = False
        self.temperature = dev["inittemp"]
        
    def getState(self):
        return self.stateEngToPU(self.temperature)
    
    def getPowerFromPU(self,pu):
        return pu*self.nominalpower
    
    def getPUFromPower(self,power):
        return power/self.nominalpower
    
    def updateSetpoint(self,new):
        if new > self.maxSetpoint:
            new = self.maxSetpoint
            
        self.setpoint = new
        
    def getActionpoints(self,mode = "lofi"):
        return self.actionpoints
    
    def getGridpoints(self,mode = "hifi"):
        if mode == "hifi":
            grid = self.gridpoints[:]
            grid.extend(self.snapstate)
            return grid
        elif mode == "lofi":
            grid = [ 0.5, 0.75, 0.9]
            grid.extend(self.snapstate)
            return grid
        elif mode == "dyn":
            dynamicgrid = []
            dynamicgrid.extend(self.snapstate)
            initstate = self.getState()            
            newstate = self.applySimulatedInput(initstate,1,30)
            if newstate <= 1 and newstate >= 0: 
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(newstate,1,60)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(initstate,0,30)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(newstate,0,60)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
        
            print("generated gridpoints dynamically for {dev}: {grd}".format(dev = self.name, grd = dynamicgrid))
            return dynamicgrid    
        
    #Euler's method, use only for relatively short time periods
    def applySimulatedInput(self,state,input,duration,pin = "default"):
        state = self.statePUToEng(state)
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
            tc = state - 6 + 273
            th = self.tamb + 4 + 273
            #print("tc: {cold}, th: {hot}, ratio: {rat}".format(cold = tc, hot = th, rat = (th/tc)))
            #efficiency = self.carnotrelativeefficiency*(1-((tc + 273)/(th + 273)))
            efficiency = self.carnotrelativeefficiency/((float(th)/float(tc))-1.0)
            peff = pin*efficiency
            state = ((-peff*input-((state - self.tamb)/self.thermR))/(self.heatcap))*step + state            
            #print("another step: after {et} seconds out of {dur} newstate is {ns}".format(et = et, dur = duration, ns = state))
        return self.stateEngToPU(state)
        
    def simulationStep(self,pin,duration):
        if pin > 0.0005:
            input = 1
            self.on = True
        else:
            input = 0
            self.on = False
        
        self.temperature = self.applySimulatedInput(self.temperature,input,duration,pin)
        self.printInfo(0)
        return self.temperature
    
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
        print(tab*depth + "STATE: {state}".format(state = self.on))
        if self.associatedbehavior:
            print(tab*depth + "BEHAVIOR:")
            self.associatedbehavior.printInfo(depth + 1)
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        
class Refrigerator(HeatPump):
    def __init__(self,**dev):
        super(Refrigerator,self).__init__(**dev)
        self.gridpoints = [0.0, 0.2, 0.4, 0.6, 0.8]
        self.statebase = 10.0
        
    def getActionpoints(self,mode = "hifi"):
        return self.actionpoints    
    
    def getGridpoints(self,mode = "hifi"):
        if mode == "hifi":
            grid = self.gridpoints[:]
            grid.extend(self.snapstate)
            return grid
        elif mode == "lofi":
            grid = [ 0.0, 0.4, 0.8]
            grid.extend(self.snapstate)
            return grid
        elif mode == "dyn":
            dynamicgrid = []
            dynamicgrid.extend(self.snapstate)
            initstate = self.getState()            
            newstate = self.applySimulatedInput(initstate,1,30)
            if newstate <= 1 and newstate >= 0: 
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(newstate,1,60)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(initstate,0,30)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
            newstate = self.applySimulatedInput(newstate,0,60)
            if newstate <= 1 and newstate >= 0:
                dynamicgrid.append(newstate)
        
            print("generated gridpoints dynamically for {dev}: {grd}".format(dev = self.name, grd = dynamicgrid))
            return dynamicgrid
        
            
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
        
        
class NoDynamics(Device):
    def __init__(self,**dev):
        super(NoDynamics,self).__init__(**dev)
        self.gridpoints = [0, 1]
        self.actionpoints = [0, 1]
        
        self.on = False
    
    def getState(self):
        if self.on:
            return 1
        else:
            return 0
        
    def getActionpoints(self,mode = "hifi"):
        return self.actionpoints
    
    def getGridpoints(self,mode = "hifi"):
        return self.gridpoints
    
    #the state becomes whatever the input tells it to be
    def applySimulatedInput(self,state,input,duration,pin = "default"):
        return input
    
    def simulationStep(self,pin,duration):
        if pin > 0:
            self.on = True
        else:
            self.on = False
        print("power in: {pow}".format(pow = pin))
        self.printInfo(0)
        return self.on
    
    def inputCostFn(self,puaction,period,state,duration):
        power = self.getPowerFromPU(puaction)
        #print("temporary debug: cost: {cost}, power: {pow}, duration: {dur}".format(cost = period.expectedenergycost, pow = power, dur = duration))
        return power*duration*period.expectedenergycost 
    
    def getPowerFromPU(self,pu):
        return pu*self.nominalpower
    
    def getPUFromPower(self,power):
        return power/self.nominalpower
    
        
class Light(NoDynamics):
    def __init__(self,**dev):
        super(Light,self).__init__(**dev)        
        
    def printInfo(self,depth = 0):
        tab = "    "
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print(tab*depth + "DEVICE SUMMARY FOR LIGHT: {me}".format(me = self.name))
        print(tab*depth + "OWNER: {own}".format(own = self.owner))
        print(tab*depth + "ON: {state}".format(state = self.on))
        if self.associatedbehavior:
            print(tab*depth + "BEHAVIOR:")
            self.associatedbehavior.printInfo(depth + 1)
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
    