from DCMGClasses.CIP import tagClient
from DCMGClasses.resources import resource, customer
from DCMGClasses.resources.misc import faults

import operator
from __builtin__ import True

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
        
        self.demandBidList = []
        self.supplyBidList = []
        self.reserveBidList = [] 
        
    def rebuildpriorities(self):
        self.nodeprioritylist = []
        self.loadprioritylist = []
        self.nodeprioritylist.extend(self.nodes)
        self.loadprioritylist.extend(self.customers)
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
        
    def hasGroundFault(self):
        for node in self.nodes:
            if node.hasGroundFault():
                return True
        return False
    
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
        newfault = faults.GroundFault("suspected",self)
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
            print("inftags: {inf}".format(inf = inftags))
        
        total = 0        
        for edge in self.interzonaledges:
            if edge.startNode in self.nodes:
                total -= infcurrents.get(edge.currentTag)
            elif edge.endNode in self.nodes:
                total += infcurrents.get(edge.currentTag)
            else:
                pass
            
            print "total: {tot} after {nam}".format(tot = total,nam=edge.name)
            
        return total
    
    
    def isolateZone(self):
        print("isolating zone {nam}".format(nam = self.name))
        for edge in self.interzonaledges:
            edge.openRelays()
    
    
    def findinterzonaledges(self):
        for node in self.nodes:
            for edge in node.originatingedges:
                if edge.endNode not in self.nodes:
                    if edge not in self.interzonaloriginatingedges:
                        self.interzonaloriginatingedges.append(edge)
                    if edge not in self.interzonaledges:
                        self.interzonaledges.append(edge)
            for edge in node.terminatingedges:
                if edge.startNode not in self.nodes:
                    if edge not in self. interzonalterminatingedges:
                        self.interzonalterminatingedges.append(edge)
                    if edge not in self.interzonaledges:
                        self.interzonaledges.append(edge)
                        
    def printInfo(self,depth=0):
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
        
        print("adding new edge between {nam} and {oth}".format(nam = self.name, oth = otherNode.name))
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
            return
        
        self.edges.append(newedge)
        otherNode.edges.append(newedge)
        
        newedge.printInfo()
        
        #identify interzonal edges
        if self.zone:
            if otherNode not in self.zone.nodes:
                self.zone.interzonaledges.append(newedge)
                if dir =="to":
                    self.zone.interzonaloriginatingedges.append(newedge)
                elif dir == "from":
                    self.zone.interzonalterminatingedges.append(newedge)
        #for the other node too
        if otherNode.zone:
            if self not in otherNode.zone.nodes:
                otherNode.zone.interzonaledges.append(newedge)
                if dir == "to":
                    otherNode.zone.interzonalterminatingedges.append(newedge)
                elif dir == "from":
                    otherNode.zone.interzonaloriginatingedges.append(newedge)
            
            
        for relay in relays:
            relay.owningEdge = newedge
            #self.relays.append(relay)
                    
        return newedge
        
    def removeEdge(self,otherNode):
        for edge in self.edges:
            if edge.startNode is self or edge.endNode is self:
                otherNode.edges.remove(edge)
                self.edges.remove(edge)
                
    def hasGroundFault(self):
        for fault in self.faults:
            if fault.__class__.__name__ == "GroundFault":
                if self in fault.faultednodes:
                    print("node {nam} has ground fault".format(nam = self.name))
                    fault.printInfo()
                    return True
        return False
                
                
        
class Node(BaseNode):
    def __init__(self, name, **kwargs):
        super(Node,self).__init__(name, **kwargs)
        self.savedstate = {}
        
        self.priorityscore = 0
        self.loadprioritylist = []
        
        self.grid, self.branch, self.bus = self.name.split(".")
        if self.grid == "DC":
            if self.branch != "MAIN":
                self.branchNumber = self.branch[-1]
                self.busNumber = self.bus[-1]
                
            if self.branch != "MAIN":
                self.voltageTag = "BRANCH_{branch}_BUS_{bus}_Voltage".format(branch = self.branchNumber, bus = self.busNumber)
            else:
                self.voltageTag = "MAIN_BUS_Voltage"
        elif self.grid == "AC":
            pass
        else:
            pass
        
#         for edge in self.edges:
#             for relay in edge.relays:
#                 savedstate[relay] = None
                
    def rebuildpriorities(self):
        self.loadprioritylist = []
        self.loadprioritylist.extend(self.customers)
        self.loadprioritylist.sort(key = operator.attrgetter("priorityscore"))
        
    def getVoltage(self):
                    
        return tagClient.readTags([self.voltageTag])
    
    
    
    def addCustomer(self,cust):
        self.customers.append(cust)
        custnode = BaseNode(cust.name + "Node")
        custrelay = Relay(cust.relayTag,"load")
        custedge = self.addEdge(custnode,"to",cust.currentTag, [custrelay])
        self.priorityscore += cust.priorityscore
        self.rebuildpriorities()
        
        return custnode, custrelay, custedge
    
    def addResource(self,res):   
        self.resources.append(res)
        if res.issource:
            if hasattr(res,"DischargeChannel"):
                self.addEdge(BaseNode(res.name + "OutNode"),"from",res.DischargeChannel.regItag,[Relay(res.DischargeChannel.relayTag,"source")])
            else:
                self.addEdge(BaseNode(res.name + "OutNode"),"from",res.dischargeCurrentTag,[Relay(res.relayTag,"source")])
        if res.issink:
            if hasattr(res,"ChargeChannel"):
                self.addEdge(BaseNode(res.name+ "InNode"),"to",res.ChargeChannel.unregItag,[Relay(res.ChargeChannel.relayTag,"source")])
            else:
                self.addEdge(BaseNode(res.name+ "InNode"),"to",res.chargeCurrentTag,[Relay(res.relayTag,"source")])
    
    def isolateNode(self):
        print("Isolating node {nam}".format(nam = self.name))
        
        for edge in self.edges:
            print("looking at edge {nam}".format(nam=edge.name))
            for relay in edge.relays:
                print("saving relay state: {nam} was {sta}".format(nam=relay.tagName, sta=relay.closed))
                #first, record the state we were in before
                self.savedstate[relay] = relay.closed
            #then, open the relays
            edge.openRelays()
        
        for key in self.savedstate:
            print key
                    
    def restorehard(self):        
        print("Restoring node {nam} HARD".format(nam = self.name))
        for edge in self.edges:
            for relay in edge.relays:
                print("closing relay {nam}".format(nam = relay.tagName))
                if self.savedstate[relay]:
                    relay.closeRelay()
                    
    def restore(self):
        print("Restoring node {nam} without impacting faulted nodes".format(nam = self.name))
        for edge in self.originatingedges:
            if edge.endNode.hasGroundFault():
                for relay in edge.relays:
                    print("won't close relay {nam} because it belongs to a faulted node ({nod})".format(nam = relay.tagName, nod = edge.endNode.name))
            else:
                for relay in edge.relays:
                    print("closing relay {nam}".format(nam = relay.tagName))
                    if self.savedstate[relay]:
                        relay.closeRelay()
        
        for edge in self.terminatingedges:
            if edge.startNode.hasGroundFault():
                for relay in edge.relays:
                    print("won't close relay {nam} because it belongs to a faulted node ({nod})".format(nam = relay.tagName, nod = edge.startNode.name))
            else:
                for relay in edge.relays:
                    print("closing relay {nam}".format(nam = relay.tagName))
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
        
        #update the zones' lists of interzonal edges
#         if self.startNode.zone:
#             self.startNode.zone.findinterzonaledges()
#         if self.endNode.zone:
#             self.endNode.zone.findinterzonaledges()
        
    #checks the recorded state of the relays between two nodes against the resistance
    #measured between two nodes to assist in finding relay faults
    def checkConsistency(self):
        statemodel = self.checkRelaysClosed()
        resistance,reliable = self.getResistance()
        outdict = {}
        outdict["reliable"] = reliable
        outdict["resistance"] = resistance
        
        if resistance < 10:
            statemeas = True
        else:
            statemeas = False        
        
        outdict["measured_state"] = statemeas
        
        discrepancy = True
        if statemeas == statemodel:
            discrepancy = False
        
        outdict["discrepancy"] = discrepancy
        
        return outdict
        
        
    def getCurrent(self):
        return tagClient.readTags([self.currentTag])
    
    #determines the resistance along this edge. returns R and a boolean indicating whether
    #the measurement is reliable
    def getResistance(self):
        v1 = self.startNode.getVoltage()
        v2 = self.endNode.getVoltage()
        vdiff = v1 - v2
        i = self.getCurrent()
        if abs(i) < .0000001:
            i = .0000001
        R = vdiff/i    
        
        #are measurements accurate enough?
        if vdiff > .05 or i > .01:
            return (R,True)
        else:
            #data points are too close to the origin
            return (R,False)
        
#         if v1 > .05 and v2 > .05:
#             if vdiff > .05:
#                 return (R, True)
#             else:
#                 if i < .05:
#                     return (R,False)
#                 else:
#                     return (R,True)
#         elif v1> .05 or v2> .05:
#             return (R,True)
#         else:            
#             #unreliable
#             return (R,False)
    
    def checkRelaysClosed(self):
        for relay in self.relays:
            if not relay.getClosed():
                return False
        return True
    
    def openRelays(self):
        for relay in self.relays:
            print("opening relay {nam}".format(nam = relay.tagName))
            relay.openRelay()
    
    def closeRelays(self):
        for relay in self.relays:
            relay.closeRelay()
    
    def getPowerFlowIn(self):
        return self.startNode.getVoltage()*self.getCurrent()
    
    def getPowerFlowOut(self):
        return self.endNode.getVoltage()*self.getCurrent()
    
    def getPowerDissipation(self):
        return abs(self.getPowerFlowIn()-self.getPowerFlowOut())
    
    def printInfo(self,depth = 0):
        spaces = "    "
        print(spaces*depth + "BEGIN EDGE CONNECTING {orig} to {term}".format(orig = self.startNode.name, term = self.endNode.name))
        print(spaces*(depth + 1) + "CURRENT TAG NAME: {tag}".format(tag = self.currentTag))
        print(spaces*(depth + 1) + "RELAYS:")
        for relay in self.relays:
            relay.printInfo(depth + 1)
        
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
        for node in self.owningNodes:
            node.setFault("relayfault")
        self.faulted = True
        
    def clearFault(self):
        for node in self.owningNodes:
            node.checkFault("relayfault")
        self.faulted = False
    
    def printInfo(self,depth = 1):
        tab = "    "
        print(depth*tab + "TAG: {tag}".format(tag = self.tagName))
        print(depth*tab + "STATE: {sta}".format(sta = self.closed))
        print(depth*tab + "FAULT: {fau}".format(fau = self.faulted))
