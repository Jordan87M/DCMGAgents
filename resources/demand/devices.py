class Device(object):
    def __init__(self, initstate):
        self.state = initstate
    
    
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "DEVICE NAME: {name}".format(name = self.name))
    
    def simulationStep(self,deltat):
        self.coeffs = self.updateCoeffs()
        self.state += self.coeffs * deltat
    
class HeatingElement(Device):
    def __init__(self,shc,mass,thermR, setpoint):
        super(Heater,self).__init__(self)
        self.shc = shc
        self.mass = mass
        self.tamb = 298
        self.thermR = thermR
        self.setpoint = setpoint
        
    def simulationStep(self,deltat,pin):
        self.coeffs = (pin - (self.state - self.tamb)/self.thermR)/(self.mass*self.shc)
        super(HeatingElement,self).simulationStep(deltat)
    
class HeatEngine(Device):
    pass