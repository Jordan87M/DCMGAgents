from DCMGClasses.CIP import tagClient
from DCMGClasses.resources import resource, customer

import operator

class Group(object):
    def __init__(self,name,resources = [], nodes = [], customers = [], **kwargs):
        self.name = name
        self.resources = resources
        self.nodes = nodes
        self.customers = customers
        
        self.rate = .1
        
        self.faults = []
        
        self.nodeprioritylist = []
        self.loadprioritylist = []
        
    def rebuildpriorities(self):
        self.nodeprioritylist = []
        self.loadprioritylist = []
        self.nodeprioritylist.extend(self.nodes)
        self.loadprioritylist.extend(self.nodes)
        self.nodeprioritylist.sort(key = operator.attrgetter("priorityscore"))
        self.loadprioritylist.sort(key = operator.attrgetter("priorityscore"))

    def addNode(self,node):
        #set node's group membership
        node.group = self
        #add node to group's list of nodes
        self.nodes.append(node)
        #add node's resources to group's
        self.resources.extend(node.resources)
        #...same for customers
        self.customers.extend(node.customers)
        
    
    def printInfo(self,depth = 0):
        spaces = "    "
        print(spaces*depth + "GROUP {me} CONTAINS THE FOLLOWING...".format(me = self.name))
        print(spaces*depth + ">>CUSTOMERS ({n}): ------------".format(n = len(self.customers)))
        for cust in self.customers:
            cust.printInfo(depth + 1)
        print(spaces*depth + "<<CUSTOMERS =END=")
        print(spaces*depth + ">>RESOURCES ({n}): ------------".format(n = len(self.resources)))
        for res in self.resources:
            res.printInfo(depth + 1)
        print(spaces*depth + "<<RESOURCES =END=")
        print(spaces*depth + ">>NODES ({n}): ----------------".format(n = len(self.nodes)))
        for node in self.nodes:
            node.printInfo(depth + 1)
        print(spaces*depth + "<<NODES =END=")
            
    
class Zone(object):
    def __init__(self,name,nodes = []):
        self.name = name
        self.nodes = nodes
        
        self.resources = []
        self.customers = []
        self.group = []
        self.edges = []
        
        self.nodeprioritylist = nodes.sort(key = operator.attrgetter("priorityscore"))

        self.faults = []
        
        self.interzonaledges = []
        self.interzonaloriginatingedges = []
        self.interzonalterminatingedges = []
        
        for node in self.nodes:            
            node.zone = self
            
        self.findinterzonaledges()
        
        
    def hasGroundFault(self):
        for node in self.nodes:
            if node.hasGroundFault():
                return True
        return False
        
    def rebuildpriorities(self):
        self.nodeprioritylist = []
        self.nodeprioritylist.extend(self.nodes)
        self.nodeprioritylist.sort(key = operator.attrgetter("priorityscore"))
            
    def newGroundFault(self):
        newfault = GroundFault("suspected")
        self.faults.append(newfault)
        newfault.owners.append(self)
        for node in self.nodes:
            node.faults.append(newfault)
            newfault.owners.append(node)
        return newfault
            
            
    def sumCurrents(self):
        inftags = []
        for edge in self.interzonaledges:
            inftags.append(edge.currentTag)
        
        if len(inftags) > 0:
            infcurrents = tagClient.readTags(inftags)
        
        total = 0        
        for edge in self.interzonaledges:
            if edge.startNode is self:
                total -= infcurrents.get(edge.currentTag)
            elif edge.endNode is self:
                total += infcurrents.get(edge.currentTag)
            else:
                pass
        return total
    
    
    def isolateZone(self):
        for edge in self.interzonaledges:
            edge.openRelays()
    
    
    def findinterzonaledges(self):
        for node in self.nodes:
            for edge in node.originatingedges:
                if edge.endNode not in self.nodes:
                    self.interzonaloriginatingedges.append(edge)
            for edge in node.terminatingedges:
                if edge.startNode not in self.nodes:
                    self.interzonalterminatingedges.append(edge)
                    
    def printInfo(self,depth):
        spaces = '    '
        print(spaces*depth + "ZONE {me}:".format(me = self.name))
        for key in self.faults:
            print(spaces*depth + "FAULT - {flt}".format(flt = key))
        print(spaces*depth + "ZONE {me} CONTAINS THE FOLLOWING...".format(me = self.name))
        print(spaces*depth + ">>NODES ({n}):".format(n = len(self.customers)))
        for cust in self.customers:
            cust.printInfo(depth + 1)
        print(spaces*depth + ">>INTERZONAL CONNECTIONS ({n}):".format(n = len(self.edges)))
        for edge in self.interzonaledges:
            edge.printInfo(depth + 1)
            
    def setfault(self,):
        self.group.setfault()
        
class BaseNode(object):
    def __init__(self,name, **kwargs):
        self.name = name
        #has
        self.resources = []
        self.customers = []
        
        #membership in 
        self.zone = None
        self.group = None
        
        
        self.faults = []
        
        #connections to other nodes
        self.edges = []
        self.originatingedges = []
        self.terminatingedges = []
        
    def addEdge(self,otherNode,dir,currentTag,relays):
        
        if dir == "to":
            newedge = DirEdge(self,otherNode,currentTag,relays)
            self.originatingedges.append(newedge)
            otherNode.terminatingedges.append(newedge)
        elif dir == "from":
            newedge = DirEdge(otherNode,self,currentTag,relays)
            self.terminatingedges.append(newedge)
            otherNode.originatingedges.append(newedge)
        else:
            print("addEdge() didn't do anything. The dir parameter must be 'to' or 'from'. ")
        
        for relay in relays:
            relay.owningEdge = newedge
                    
        self.edges.append(newedge)
        otherNode.edges.append(newedge)
        
    def removeEdge(self,otherNode):
        for edge in self.edges:
            if edge.startNode is self or edge.endNode is self:
                otherNode.edges.remove(edge)
                self.edges.remove(edge)
                
        
class Node(BaseNode):
    def __init__(self, name, **kwargs):
        super(Node,self).__init__(name, **kwargs)
        savedstate = {}
        
        self.priorityscore = 0
        self.loadprioritylist = []
        
        self.grid, self.branch, self.bus = self.name.split(".")
        if self.branch != "MAIN":
            self.branchNumber = self.branch[-1]
            self.busNumber = self.bus[-1]
            
    def rebuildpriorities(self):
        self.loadprioritylist = []
        self.loadprioritylist.extend(self.customers)
        self.loadprioritylist.sort(key = operator.attrgetter("priorityscore"))
        
    def getVoltage(self):
        if self.branch != "MAIN":
            signal = "BRANCH_{branch}_BUS_{bus}_Voltage".format(branch = self.branchNumber, bus = self.busNumber)
        else:
            signal = "MAIN_BUS_Voltage"
            
        return tagClient.readTags([signal])
    
    def hasGroundFault(self):
        for fault in self.faults:
            if fault.__class__.__name__ == "GroundFault":
                return True
        return False
    
    def addCustomer(self,cust):
        self.customers.append(cust)
        custnode = BaseNode(cust.name + "Node")
        self.addEdge(custnode,"to",cust.currentTag, [Relay(cust.relayTag,"load")])
        self.priorityscore += cust.priorityscore
        self.rebuildpriorities()
    
    def addResource(self,res):   
        self.resources.append(res)
        if hasattr(res,"DischargeChannel"):
            self.addEdge(BaseNode(res.name + "OutNode"),"from",res.DischargeChannel.regItag,[Relay(res.DischargeChannel.relayTag,"source")])
        if hasattr(res,"ChargeChannel"):
            self.addEdge(BaseNode(res.name+ "InNode"),"to",res.ChargeChannel.unregItag,[Relay(res.ChargeChannel.relayTag,"source")])
    
    def isolateNode(self):
        for edge in self.edges:
            for relay in  edge.relays:
                #first, record the state we were in before
                self.savedstate[relay] = relay.closed
            #then, open the relays
            edge.openRelays()
            
    def restore(self):
        for edge in self.edges:
            for relay in edge.relays:
                if self.savedstate[relay]:
                    relay.closeRelay()
            
    def sumCurrents(self):
        inftags = []
        for edge in self.edges:
            if edge.currentTag is not None and len(edge.currentTag) > 0:
                inftags.append(edge.currentTag)
        
        if len(inftags) > 0:
            infcurrents = tagClient.readTags(inftags)
        
        total = 0
        for edge in self.edges:
            if edge.currentTag is not None and len(edge.currentTag) > 0:
                if edge.startNode is self:
                    total -= infcurrents.get(edge.currentTag)
                elif edge.endNode is self:
                    total += infcurrents.get(edge.currentTag)
                else:
                    pass        
        
        return total
    
    def printInfo(self,depth = 0,verbosity = 1):
        spaces = '    '
        print(spaces*depth + "NODE {me} PROBLEMS:".format(me = self.name))
        for fault in self.faults:
            fault.printInfo(depth + 1)
        print(spaces*depth + " MEMBER OF ZONE: {zon}".format(zon = self.zone.name))
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
    
    #propagate fault up to zonal level        
    def setFault(self,fault):
        if self.faults.get("fault",None) is not None:
            self.faults["fault"] = True
            self.zone.setFault(fault)
    
    #checks to see if all faults associated with node have been cleared
    #if they have been, clear the node's fault and propagate checkfault
    #to the zonal level
    def checkFault(self,fault):
        if fault == "relayfault":
            faulted = False
            for edge in self.edges:
                for relay in edge.relays:
                    if relay.faulted:
                        faulted = True
                        return True
            if not faulted:
                self.faults[fault] = False
                self.zone.checkFault()
        if fault == "groundfault":
            pass
        if fault == "lowvoltage":
            pass
    
class DirEdge(object):
    def __init__(self, startNode, endNode, currentTag, relays):
        self.startNode = startNode
        self.endNode = endNode
        self.currentTag = currentTag
        
        self.relays = relays
        self.name = "from" + self.startNode.name + "to" + self.endNode.name
    #checks the recorded state of the relays between two nodes against the resistance
    #measured between two nodes to assist in finding relay faults
    def checkConsistency(self):
        statemodel = self.checkRelaysOpen()
        resistance,reliable = self.getResistance()
        if reliable:
            if resistance < 10:
                statemeas = True
            else:
                statemeas = False
            
                
            if statemeas or statemodel:
                if statemeas and statemodel:
                    return ("open", True)
                else:
                    return(statemeas, False)
            if not statemeas and not statemodel:                
                return ("closed", True)
        
    def getCurrent(self):
        return tagClient.readTags([self.currentTag])
    
    #determines the resistance along this edge. returns R and a boolean indicating whether
    #the measurement is reliable
    def getResistance(self):
        v1 = self.startNode.getVoltage()
        v2 = self.endNode.getVoltage()
        vdiff = v1 - v2
        i = self.getCurrent()
        if abs(i) < .0001:
            i = .0001
        R = vdiff/i    
        
        if v1 > .05 and v2 > .05:
            if vdiff > .05:
                return (R, True)
            else:
                if i < .05:
                    return (R,False)
                else:
                    return (R,True)
        else:
            #unreliable
            return (R,False)
    
    def checkRelaysClosed(self):
        for relay in self.relays:
            if not relay.getClosed():
                return False
        return True
    
    def openRelays(self):
        for relay in self.relays:
            relay.openRelay()
    
    def closeRelays(self):
        for relay in self.relays:
            relay.closeRelay()
    
    def getPowerFlowIn(self):
        return self.startNode.getVoltage()*self.getCurrent()
    
    def getPowerFlowOut(self):
        return self.endNode.getVoltage()*self.getCurrent()
    
    def printInfo(self,depth = 0):
        spaces = "    "
        print(spaces*depth + "BEGIN EDGE CONNECTING {orig} to {term}".format(orig = self.startNode.name, term = self.endNode.name))
        print(spaces*(depth + 1) + "CURRENT TAG NAME: {tag}".format(tag = self.currentTag))
        
class Relay(object):
    def __init__(self,tagname,type):
        self.owningNodes = []
        self.owningEdges = []
        self.type =  type
        self.tagName = tagname
        
        self.closed = None
        self.faulted = False
        
    def getClosed(self):
        #return self.closed
        retval = tagClient.readTags([self.tagName])
        retval = not retval
        self.closed = retval
        return retval
    
    def closeRelay(self):
        if self.type == "infrastructure":
            tagClient.writeTags([self.tagName],[False])
        elif self.type == "load" or self.type == "source":
            tagClient.writeTags([self.tagName],[True])
        self.closed = True
    
    def openRelay(self):
        if self.type == "infrastructure":
            tagClient.writeTags([self.tagName],[True])
        elif self.type == "load" or self.type == "source":
            tagClient.writeTags([self.tagName],[False])
        self.closed = False
        
    def setFault(self):
        self.owningNode.setFault("relayfault")
        self.faulted = True
        
    def clearFault(self):
        self.owningNode.checkFault("relayfault")
        self.faulted = False
        
