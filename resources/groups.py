from DCMGClasses.CIP import tagClient
from DCMGClasses.resources import resource, customer

class Group(object):
    def __init__(self,name,resources = [],membership = [], customers = [], **kwargs):
        self.name = name
        self.resources = resources
        self.membership = membership
        self.customers = customers
        
        self.rate = .1
        
        #state flags
        self.voltageLow = True
        self.groundfault = False
        self.relayfault = False
        
        
        
    def printInfo(self,verbosity = 1):
        print(">>>>GROUP {me} CONTAINS THE FOLLOWING...".format(me = self.name))
        print(">>>>>>>CUSTOMERS ({n}): ------------".format(n = len(self.customers)))
        for cust in self.customers:
            cust.printInfo()
        print(">>>>>>>RESOURCES ({n}): ------------".format(n = len(self.resources)))
        for res in self.resources:
            res.printInfo()
        print(">>>>>>>NODES ({n}): ----------------".format(n = len(self.membership)))
        for mem in self.membership:
            mem.printInfo()
            
    def getAvgVoltage(self):
        sum = 0
        for node in self.membership:
            sum += node.getVoltage()
        return sum/len(self.membership)
        
    
class Node(object):
    def __init__(self,name,resources = [], membership = None, customers = [], currentTags = [], **kwargs):
        self.name = name 
        self.resources = resources
        self.membership = membership
        self.customers = customers
        self.currentTags = currentTags
        self.state = "normal"
        
        self.grid, self.branch, self.bus = self.name.split(".")
        if self.branch != "MAIN":
            self.branchNumber = self.branch[-1]
            self.busNumber = self.bus[-1]
            
        #state flags
        self.voltageLow = True
        self.groundfault = False
        self.relayfault = False
        
    def sumCurrents(self):
        infcurrents = tagClient.readTags(self.currentTags)
        total = 0
        for current in infcurrents:
            total += infcurrents[current]        
        return total
        
    def getVoltage(self):
        if self.branch != "MAIN":
            signal = "BRANCH_{branch}_BUS_{bus}_Voltage".format(branch = self.branchNumber, bus = self.busNumber)
        else:
            signal = "MAIN_BUS_Voltage"
            
        return tagClient.readTags([signal])
        
    
    def getCurrent(self):
        if self.branch != "MAIN":
            signal = "BRANCH_{branch}_BUS_{bus}_Current".format(branch = self.branchNumber, bus = self.busNumber)
        else:
            signal = "MAIN_BUS_Current"
        return tagClient.readTags([signal])
        
        
    def getPowerFlow(self):
        return self.getVoltage()*self.getcurrent()
    
    def isolateNode(self):
        if self.branch == "MAIN":
            signals = ["BRANCH_1_BUS_1_PROX_DUMMY","BRANCH_2_BUS_1_PROX_DUMMY"]
            tagClient.writeTags(signals,[True, True])
        else:
            signals = ["BRANCH_{branch}_BUS_{bus}_DIST_DUMMY", "BRANCH_{branch}_BUS_{bus}_DIST_PROX_DUMMY"]
            tagClient.writeTags(signals,[True, True])
    
    def printInfo(self,verbosity = 1):
        print("NODE {me} CONTAINS THE FOLLOWING...".format(me = self.name))
        print(">>CUSTOMERS ({n}):".format(n = len(self.customers)))
        for cust in self.customers:
            cust.printInfo()
        print(">>RESOURCES ({n}):".format(n = len(self.resources)))
        for res in self.resources:
            res.printInfo()