from volttron.platform.vip.agent import core

import random

class Fault(object):
    def __init__(self,state = "suspected"):
        self.state = state
        self.owners = []
        self.uid = random.getrandbits(32)
        
    def remAllExcept(self,keep):
        if keep in self.owners:
            for owner in self.owners:
                if owner is not keep:
                    self.owners.remove(owner)
        else:
            pass
        
    #fault has been cleared, restore nodes and unlink fault object
    def cleared(self):
        for owner in self.owners:
            if owner in self.isolatednodes or owner in self.faultednodes:
                if owner.__class__.__name__ == "Node":
                    self.restorenode(owner)
            if self in owner.faults:
                owner.faults.remove(self)
                
            self.owners.remove(owner)
        
class GroundFault(Fault):
    def __init__(self,state,zone):
        super(GroundFault,self).__init__(state)
        self.reclose = True
        self.isolatednodes = []
        self.faultednodes = []
        self.reclosecounter = 0
        self.reclosemax = 2
        self.zone = zone
        
        
    def isolateNode(self,node):
        if node in self.owners:
            node.isolateNode()
            self.isolatednodes.append(node)
            
    def forcerestorenode(self,node):
        if node in self.owners:
            node.restorehard()
            
            if node in self.isolatednodes:
                self.isolatednodes.remove(node)
                
            if node in self.faultednodes:
                self.faultednodes.remove(node)
    
    def restorenode(self,node):
        print("restoring node {nam}".format(nam = node.name))
        if node in self.owners:
            node.restore()
            
            if node in self.isolatednodes:
                self.isolatednodes.remove(node)
            
            if node in self.faultednodes:
                self.faultednodes.remove(node)
    
    def reclosezone(self):        
        self.reclosecounter += 1
        for node in self.zone.nodes:
            self.reclosenode(node)
            
        if self.reclosecounter == self.reclosemax:
            self.reclose = False
    
    def reclosenode(self,node):
        #self.reclosecounter += 1 #now done in reclosezone()
        self.forcerestorenode(node)
        
    
        
    def printInfo(self,depth = 0):
        tab = "    "
        print(tab*depth + "FAULT: {id}".format(id = self.uid))
        print(tab*depth + "STATE: {sta}".format(sta = self.state))
        print(tab*depth + "-RECLOSES LEFT: {amt} of {max}".format(amt = self.reclosemax-self.reclosecounter, max = self.reclosemax))
        print(tab*depth + "-AFFECTED NODES and ZONES")
        for owner in self.owners:
            print(tab*depth + "--" + owner.name)
            if owner in self.isolatednodes:
                print("... CURRENTLY ISOLATED ...")
            if owner in self.faultednodes:
                print("!!! FAULT LOCATED HERE!!!")
                
                
class RemedialAction(object):
    def __init__(self):        
        utilbefore = None
        utilafter = None
        
        
class GroupMerger(RemedialAction):
    def __init__(self,edge):
        super(GroupMerger,self).__init__()
        
        self.edge = edge
        self.utilafter = self.getutilafter()
        
    def getutilbefore(self):
        pass
    
    #ideally would use a model to determine consequences of action
    #for now, find an edge that is closer to more nodes with more important stuff
    def getutilafter(self):
        score = 0.0
        visitedlist = []
        keepgoing = True
        factor = 0.5
        
        expandstack = []
        expandstack.append(self.edge.endNode)
        visitedlist.append(self.edge.endNode)
        
        expandstack.append(self.edge.startNode)
        visitedlist.append(self.edge.startNode)
        
        distance = 1        
        #while expandstack is not empty
        print("temp debug: beginning to work on {edg}".format(edg = self.edge.name))
        while expandstack:           
            print("temp debug: expandstack --")
            for node in expandstack:
                print("node: {nam}".format(nam=node.name))
                
            #new round of end nodes to be expanded
            newnodes = []       
            
            #list of nodes to remove
            remnodes = []     
            
            #for each node in expandstack add all unique neighboring nodes
            for node in expandstack:         
                
                print("temp debug: expanding node {nam}".format(nam = node.name))
                
                #remove the node when it is investigated       
                remnodes.append(node)
                
                #if the node has a priority score...
                if hasattr(node,"priorityscore"):
                    #add the priority score inversely weighted by its distance from the edge
                    
                    contrib = node.priorityscore*(factor**distance)
                    score += contrib
                    
                    print("temp debug: node contribution: {con}".format(con=contrib))
                    
                    #add nodes to the the list of unexpanded nodes
                    for edge in node.originatingedges:
                        #if the node has not already been visited
                        if edge.endNode not in visitedlist:
                            #if the node does not have a ground fault
                            if edge.endNode.hasGroundFault():
                                pass
                            else:
                                #add to list of visited nodes so that it won't be expanded again
                                visitedlist.append(edge.endNode)
                                newnodes.append(edge.endNode)
                    
                    for edge in node.terminatingedges:
                        if edge.startNode not in visitedlist:
                            if edge.startNode.hasGroundFault():
                                pass
                            else:
                                visitedlist.append(edge.startNode)
                                newnodes.append(edge.startNode)
                                
            #remove expanded nodes from expand stack
            for node in remnodes:
                expandstack.remove(node)
                
            #add new nodes to expand stack
            expandstack.extend(newnodes)
            #all nodes are 1 step further from the edge
            distance += 1
            
            print("temp debug: total score is {sco}".format(sco = score))            
            for node in newnodes:
                print("temp debug: add node {nam} to expand stack".format(nam=node.name ))
        
        print("temp debug: final score is {sco}".format(sco = score))
        return score
    
    def getutils(self):
        pass
            