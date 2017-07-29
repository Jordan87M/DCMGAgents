from multidimarray import initarray

def generateStates(inputs,grid,nextgrid):
    for state in grid:
        for u in inputs:
            totalcost = 0
            for dev in u.devices:
                statecost = dev.costFn(state[dev.name])
                [endstate, controlcost] = dev.previewstep(state[dev.name],u[dev.name])
                stepcost = statecost + controlcost;
                #interpolate optimal cost from end state
                nextstepopt = dpinterp(endstate,nextstate)
                
                                
class StateGrid(object):
    def __init__(self,dimensions):
        self.grid = initarray(dimensions,-1)
        
    def getPoint(self,indices):
        a = self.grid
        for index in indices:
            a = a[index]
        return a
    
    def setPoint(self,indices,value):
        a = self.grid
        for index in indices:
            if index == indices[-1]:
                a[index] = value
            else:
                a = a[index]
            
    def interpolate(self,values):
        #first find which indices bracket the point
        indices = [0]*len(values)
        for value in values:
            pass
            
    def interpolateDimension(self,dimension,value):
        pass
                
        
class StateGridPoint(object):
    def __init__(self,components):
        self.cost = cost
        
        self.components = components
        
        self.optimalinput = None
        
    
class InputSignal(object):
    def __init__(self,comps,gridconnected,drpart):
        self.gridconnected = gridconnected
        self.drevents = drpart
        self.components = comps
        self.transcost = None
        self.pathcost = None
    
    #sets cost of transition associated with input
    #returns old the old cost
    def setcost(self,cost):
        temp = self.transcost
        self.transcost = cost
        return temp

    
