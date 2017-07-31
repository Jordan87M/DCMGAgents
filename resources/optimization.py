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
            
    def interpolate(self,x):
        #use inverse distance weighting interpolation
        
        #power to which distance should be raised
        p = 4
        
        nsum = 0
        dsum = 0
        for point in grid:
            #if the point falls directly on a grid point, just use that point's value
            if point.components == x:
                return point.optimalinput.pathcost
            
            d = self.getdistance(x,point.components)
            w = d**-p
            dsum += w
            nsum += w*point.optimalinput.pathcost
            
        return nsum/dsum
            
    def getdistance(a,b):
        sumsq = 0
        for key in a:
            sumsq += (a[key] - b[key])**2
        return sumsq ** .5
                
        
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

    
