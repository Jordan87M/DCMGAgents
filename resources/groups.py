from DCMGClasses.CIP import tagClient

class Group(object):
    def __init__(self,name,resources = [],membership = [], customers = [], **kwargs):
        self.name = name
        self.resources = resources
        self.membership = membership
        self.customers = customers
        
        self.security = -1
        
class Node(object):
    def __init__(self,name,resources = [], membership = [], customers = [], **kwargs):
        self.name = name 
        self.resources = resources
        
        self.grid, self.branch, self.bus = self.name.split(".")
        
    def getVoltage(self):
        if self.branch != "MAIN":
            signal = "BRANCH{branch}_BUS{bus}_Voltage".format(branch = self.branch, bus = self.bus)
        else:
            signal = "MAIN_BUS_Voltage"
            
        resdict = tagClient.readTags([signal])
        return resdict[signal]
    
    def getCurrent(self):
        if self.branch != "MAIN":
            signal = "BRANCH{branch}_BUS{bus}_Current".format(branch = self.branch, bus = self.bus)
        else:
            signal = "MAIN_BUS_Current"
        resdict = tagClient.readTags([signal])
        return resdict[signal]
        
    def getPowerFlow(self):
        return self.getVoltage()*self.getcurrent()
    
    def isolateNode(self):
        if self.branch == "MAIN":
            signals = ["BRANCH1_BUS1_PROX_DUMMY","BRANCH2_BUS1_PROX_DUMMY"]
            writeTags(signals,[True, True])
        else:
            signals = ["BRANCH{branch}_BUS{bus}_DIST_DUMMY", "BRANCH{branch}_BUS{bus}_DIST_PROX_DUMMY"]
            writeTags(signals,[True, True])
    
    