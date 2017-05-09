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
        
        
    def printInfo(self,depth = 0):
        spaces = "    "
        print(spaces*depth + ">>>>GROUP {me} CONTAINS THE FOLLOWING...".format(me = self.name))
        print(spaces*depth + ">>>>>>>CUSTOMERS ({n}): ------------".format(n = len(self.customers)))
        for cust in self.customers:
            cust.printInfo(depth + 1)
        print(spaces*depth + ">>>>>>>CUSTOMERS =END=")
        print(spaces*depth + ">>>>>>>RESOURCES ({n}): ------------".format(n = len(self.resources)))
        for res in self.resources:
            res.printInfo(depth + 1)
        print(spaces*depth + ">>>>>>>RESOURCES =END=")
        print(spaces*depth + ">>>>>>>NODES ({n}): ----------------".format(n = len(self.membership)))
        for mem in self.membership:
            mem.printInfo(depth + 1)
        print(spaces*depth + ">>>>>>>NODES =END=")
            
    def getAvgVoltage(self):
        sum = 0
        for node in self.membership:
            sum += node.getVoltage()
        return sum/len(self.membership)
        
class BaseNode(object):
    def __init__(self,name,resources = [], membership = None):
        self.name = name
        self.resources = resources
        self.membership = None
        self.edges = []
        
    def addEdge(self,otherNode,dir,currentTag):
        if dir == "from":
            self.edges.append(DirEdge(otherNode,self,currentTag))
        elif dir == "to":
            self.edges.append(DirEdge(self,otherNode,currentTag))
        else:
            print("addEdge() didn't do anything. The dir paramter must be 'to' or 'from'. ")
        
        
    def removeEdge(self,otherNode):
        for edge in self.edges:
            if edge.startNode is self or edge.endNode is self:
                edges.remove(edge)
    
        
class Node(BaseNode):
    def __init__(self,name,resources = [], membership = None, customers = [], **kwargs):
        super(self,Node).__init__(name,resources, membership)
        self.customers = customers
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
        #infcurrents = tagClient.readTags(self.currentTags)
        inftags = []
        for edge in self.edges:
            inftags.append(edge.currentTag)
        
        infcurrents = tagClient.readTags(inftags)
            
        total = 0        
        for edge in self.edges:
            if edge.startNode is self:
                total -= infcurrents.get(edge.currentTag)
            elif edge.endNode is self:
                total += infcurrents.get(edge.currentTag)
            else:
                pass        
        
        return total
        
    def getVoltage(self):
        if self.branch != "MAIN":
            signal = "BRANCH_{branch}_BUS_{bus}_Voltage".format(branch = self.branchNumber, bus = self.busNumber)
        else:
            signal = "MAIN_BUS_Voltage"
            
        return tagClient.readTags([signal])
    
    def addCustomer(self,cust):
        self.customers.append(cust)
        self.addEdge(BaseNode(cust.name + "Node", cust.Resources, self.membership),"to",cust.currentTag)
    
    def addResource(self,res,currentTag = None):   
        self.resources.append(res)
        if currentTag:
            self.addEdge(BaseNode(res.name + "Node", res, None),"from",currentTag)
    
    def isolateNode(self):
        if self.branch == "MAIN":
            signals = ["BRANCH_1_BUS_1_PROX_DUMMY","BRANCH_2_BUS_1_PROX_DUMMY"]
            tagClient.writeTags(signals,[True, True])
        else:
            signals = ["BRANCH_{branch}_BUS_{bus}_DIST_DUMMY", "BRANCH_{branch}_BUS_{bus}_DIST_PROX_DUMMY"]
            tagClient.writeTags(signals,[True, True])
    
    def printInfo(self,depth = 0,verbosity = 1):
        spaces = '    '
        print(spaces*depth + "NODE {me} PROBLEMS:".format(me = self.name))
        if self.voltageLow:
            print(spaces*depth + "FAULT: VOLTAGE BELOW SPEC")
        if self.groundfault:
            print(spaces*depth + "FAULT: GROUNDFAULT")
        if self.relayfault:
            print(spaces*depth + "FAULT: RELAY MALFUNCTION")
        print(spaces*depth + "NODE {me} CONTAINS THE FOLLOWING...".format(me = self.name))
        print(spaces*depth + ">>CUSTOMERS ({n}):".format(n = len(self.customers)))
        for cust in self.customers:
            cust.printInfo(depth + 1)
        print(spaces*depth + ">>RESOURCES ({n}):".format(n = len(self.resources)))
        for res in self.resources:
            res.printInfo(depth + 1)
        print(spaces*depth + ">>CONNECTIONS ({n}):".format(n = len(self.edges)))
        for edge in self.edges:
            edge.printInfo(depth + 1)
 
    
class DirEdge(object):
    def __init__(self, startNode, endNode, currentTag):
        self.startNode = startNode
        self.endNode = endNode
        self.currentTag = currentTag
        
    def getCurrent(self):
        return tagClient.readTags([self.currentTag])    
    
    def getPowerFlowIn(self):
        return self.startNode.getVoltage()*self.getCurrent()
    
    def getPowerFlowOut(self):
        return self.endNode.getVoltage()*self.getCurrent()
    
    def printInfo(self,depth = 0):
        spaces = "    "
        print(spaces*depth + "BEGIN EDGE CONNECTING {orig} to {term}".format(orig = self.startNode.name, term = self.endNode.name))
        print(spaces*(depth + 1) + "CURRENT TAG NAME: {tag}".format(tag = self.currentTag))