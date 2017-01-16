from __future__ import absolute_import
from datetime import datetime, timedelta
import logging
import sys
import json
import operator

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

#from DCMGClasses.CIP import wrapper
from DCMGClasses.CIP import tagClient
from DCMGClasses.resources.misc import listparse
from DCMGClasses.resources.math import interpolation, graph
from DCMGClasses.resources import resource, groups, financial, control, customer


from . import settings
from zmq.backend.cython.constants import RATE
utils.setup_logging()
_log = logging.getLogger(__name__)

''''the UtilityAgent class represents the owner of the distribution 
infrastructure and chief planner for grid operations'''
class UtilityAgent(Agent):
    resourcePool = []
    standardCustomerEnrollment = {"message_subject" : "customer_enrollment",
                                  "message_type" : "new_customer_query",
                                  "message_target" : "broadcast",
                                  "rereg": False,
                                  "info" : ["name","location","resources","customerType"]
                                  }
    
    standardDREnrollment = {"message_subject" : "DR_enrollment",
                            "message_target" : "broadcast",
                            "message_type" : "enrollment_query",
                            "info" : "name"
                            }
    
    standardDREvent = {"message_subject" : "DR_event",
                       "event_id" : 0,
                       "event_duration": 0,
                       "event_type" : "shed"
                       }
    
    standardPowerBidSolicitation = {"message_subject": "bid_solicitation",
                               "message_target": "broadcast",
                               "service": "standard",
                               "uid":0}
    
    standardReserveBidSolicitation = {"message_subject": "bid_solicitation",
                                      "message_target": "broadcast",
                                      "service": "reserve",
                                      "uid":0}
    uid = 0
    
    
    def __init__(self,config_path,**kwargs):
        super(UtilityAgent,self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config['agentid']
        self.state = "init"
        
        self.name = self.config["name"]
        self.resources = self.config["resources"]
        self.Resources = []
        self.groupList = []
        self.bidList = []
        
        self.nodes = [groups.Node("DC.MAIN.MAIN"),
                        groups.Node("DC.BRANCH1.BUS1"),
                        groups.Node("DC.BRANCH1.BUS2"),
                        groups.Node("DC.BRANCH2.BUS1"),
                        groups.Node("DC.BRANCH2.BUS2")]
        #import list of utility resources and make into object
        resource.addResource(self.resources,self.Resources,False)
        #add resources to node objects based on location
        for res in self.Resources:
            for node in self.nodes:
                if res.location == node.name:
                    node.resources.append(res)
            
        
        self.perceivedInsol = 75 #as a percentage of nominal
        self.customers = []
        self.DRparticipants = []
        
        
        #short term planning interval counter
        self.STPinterval = 0
        self.STPlan  = control.Plan(self,self.STPinterval + 1)
        
    @Core.receiver('onstart')
    def setup(self,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        self.state = "setup"
        
        self.vip.pubsub.subscribe('pubsub','energymarket', callback = self.marketfeed)
        self.vip.pubsub.subscribe('pubsub','demandresponse',callback = self.DRfeed)
        self.vip.pubsub.subscribe('pubsub','customerservice',callback = self.customerfeed)
        self.vip.pubsub.subscribe('pubsub','weatherservice',callback = self.weatherfeed)
                
        
        self.connMatrix = [[1,1,1,0,0],[1,1,0,1,0],[1,0,1,0,1],[0,1,0,1,0],[0,0,1,0,1]]
        
        self.printInfo(2)
        #self.discoverCustomers()
    
    '''callback for weatherfeed topic'''
    def weatherfeed(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get('message_subject',None)
        messageTarget = mesdict.get('message_target',None)
        messageSender = mesdict.get('message_sender',None)
        messageType = mesdict.get("message_type",None)
        
        if listparse.isRecipient(messageTarget,self.name):    
            if messageSubject == "nowcast":
                if messageType == "solar_irradiance":
                    self.perceivedInsol = mesdict.get("info",None)
    
    '''callback for customer service topic. This topic is used to enroll customers
    and manage customer accounts.'''    
    def customerfeed(self, peer, sender, bus, topic, headers, message):
        try:
            mesdict = json.loads(message)
        except Exception as e:
            print("customerfeed message to {me} was not formatted properly".format(me = self))
            
        messageTarget = mesdict.get("message_target",None)
        if listparse.isRecipient(messageTarget,self.name):
            
            if settings.DEBUGGING_LEVEL >= 2:
                print(message)
            
            messageSubject = mesdict.get("message_subject",None)
            messageType = mesdict.get("message_type",None)
            if messageSubject == "customer_enrollment":
                print(self.customers)
                if messageType == "new_customer_response":
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("UTILITY {me} RECEIVED A RESPONSE TO CUSTOMER ENROLLMENT SOLICITATION".format(me = self.name))
                    try:
                        name, location, resources, customerType = mesdict.get("info")                        
                    except Exception as e:
                        print("customer information improperly formatted :(")
                        
                    if customerType == "residential":
                        cust = customer.ResidentialCustomerProfile(name,location,resources)
                        self.customers.append(cust)
                    elif customerType == "commercial":
                        self.customers.append(customer.CommercialCustomerProfile(name,location,resources))
                    else:                        
                        pass
                    
                    #add resources to resource pool if present
                    if resources:
                        def addOneToPool(list,res):
                            resType = res.pop("type",None)
                            if resType == "solar":
                                profile = customer.SolarProfile(**res)                                
                                #profile = customer.SolarProfile(owner,location,name,capCost,maxDischargePower)
                                
                            elif resType == "lead_acid_battery":
                                profile = customer.LeadAcidBatteryProfile(**res)                                
                                #profile = customer.LeadAcidBatteryProfile(owner,location,name,capCost,maxDischargePower,maxChargePower,capacity)
                            else:
                                print("Why am I here? {type}".format(type = resType))
                            list.append(profile)
                            
                            
                        #create new resource profile
                        #add it to resource pool
                        print(resources)
                        if type(resources) is list:
                            if len(resources) > 1:
                                for resource in resources:
                                    addOneToPool(self.resourcePool,resource)
                                    for node in self.nodes:
                                        if node.name == resource["location"]:
                                            addOneToPool(node.resources, resource) 
                            if len(resources) == 1:
                                addOneToPool(self.resourcePool,resources[0])
                                for node in self.nodes:
                                    if node.name == resources[0]["location"]:
                                        addOneToPool(node.resources, resources[0])                                
                        elif type(resources) is str or type(resources) is unicode:
                            addOneToPool(self.resourcePool,resources)
                            for node in self.nodes:
                                if node.name == resources["location"]:
                                    addOneToPool(node.resources, resources) 
                    
                    if settings.DEBUGGING_LEVEL >= 1:
                        print("UTILITY {me} enrolled customer {them}: {mes}".format(me = self.name, them = name, mes = message))
                        print(self.customers)
                    
                    resdict = {}
                    resdict["message_subject"] = "customer_enrollment"
                    resdict["message_type"] = "new_customer_confirm"
                    resdict["message_target"] = name
                    response = json.dumps(resdict)
                    self.vip.pubsub.publish(peer = "pubsub",topic = "customerservice", headers = {}, message = response)
                    
                    if settings.DEBUGGING_LEVEL >= 1:
                        print("let the customer {name} know they've been successfully enrolled by {me}".format(name = name, me = self.name))
            else:
                pass
        pass
    
    '''called to send a DR enrollment message. when a customer has been enrolled
    they can be called on to increase or decrease consumption to help the utility
    meet its goals'''    
    def solicitDREnrollment(self, name = "broadcast"):
        mesdict = {}
        mesdict["message_subject"] = "DR_enrollment"
        mesdict["message_type"] = "enrollment_query"
        mesdict["message_target"] = name
        mesdict["message_sender"] = self.name
        mesdict["info"] = "name"
        
        message = json.dumps(mesdict)
        self.vip.pubsub.publish(peer = "pubsub", topic = "demandresponse", headers = {}, message = message)
        
        if settings.DEBUGGING_LEVEL >= 1:
            print("UTILITY {name} IS TRYING TO ENROLL DR PARTICIPANTS: {mes}".format(name = self.name, mes = message))
    
    
    @Core.periodic(settings.LT_PLAN_INTERVAL)
    def planLongTerm(self):
        pass
    
    @Core.periodic(settings.ST_PLAN_INTERVAL)
    def solicitBids(self):
        if settings.DEBUGGING_LEVEL >=2 :
            print("UTILITY {me} IS ASKING FOR BIDS FOR SHORT TERM PLANNING INTERVAL {int}".format(me = self.name, int = self.STPinterval))
        subs = self.getTopology()
        self.printInfo(2)
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY {me} THINKS THE TOPOLOGY IS {top}".format(me = self.name, top = subs))
        
        '''first we have to find out how much it will cost to get power
        from various sources, both those owned by the utility and by 
        customers'''
        #clear the bid list in preparation for receiving new bids
        self.bidList = []
        #send bid solicitations to all customers who are known to have behind the meter resources
        for group in self.groupList:
            print(group.name)
            for cust in group.customers:
                print(cust.name)
                if cust.resources:
                    #ask about bulk power
                    mesdict = standardPowerBidSolicitation
                    mesdict["message_target"] = cust.name
                    mesdict["period"] = self.STPinterval
                    self.uid += 1
                    mess = json.dumps(mesdict)
                    self.vip.pubsub.publish(peer = "pubsub", topic = "energymarket", headers = {}, message = mess)
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("UTILITY {me} SOLICITING BULK POWER BID: {mes}".format(me = self.name, mes = mess))
                    #ask about reserves
                    mesdict = standardReserveBidSolicitation
                    mesdict["message_target"] = cust.name
                    mesdict["uid"] = self.uid
                    self.uid += 1
                    mess = json.dumps(mesdict)
                    self.vip.pubsub.publish(peer = "pubsub", topic = "energymarket", headers = {}, message = mess)
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("UTILITY {me} SOLICITING RESERVE POWER BID: {mes}".format(me = self.name, mes = mess))
        sched = datetime.utcnow() + timedelta(seconds = 30)            
        delaycall = Core.schedule(sched,self.planShortTerm)
        print(delaycall)
        print(dir(delaycall))
        
    def planShortTerm(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY {me} IS FORMING A NEW SHORT TERM PLAN".format(me = self.name))
           
        for group in self.groupList:
            
            self.STPlan = control.Plan(self,STPinterval + 1)
            expLoad = self.getExpectedGroupLoad(group)
            maxLoad = self.getMaxGroupLoad(group)
            #find lowest cost option for fulfilling expected demand
            #we leave determining the cost of distributed resources to their owners
            #but, we still have to figure out how to value energy from utility resources
            for res in self.Resources:
                if type(res) is SolarPanel:
                    amount = res.maxDischargePower*self.perceivedInsol/100
                    rate = financial.ratecalc(res.capCost,.05,res.amortizationPeriod,.2)
                elif type(res) is LeadAcidBattery:
                    amount = 10
                    rate = max(financial.ratecalc(res.capCost,.05,res.amortizationPeriod,.05),self.capCost/self.cyclelife) + self.avgEnergyCost*amount
                else:
                    print("trying to plan for unknown resource type")
            #sort array of bids by rate from low to high
            bidList.sort(key = operator.attrgetter("rate"))
            supply = 0      
            for bid in bidList:
                if bid.service == "power":
                    if supply < expLoad:
                        supply += bid.amount
                        if supply > expLoad:
                            #we only need part of the last bid amount
                            bid.accepted = True
                            bid.modified = True
                            bid.amount = bid.amount-(supply-expLoad)
                            #set price at the margin
                            rate = bid.rate
                            self.STPlan.wholesaleRate = rate
                            self.STPlan.addbid(bid)
                        else:
                            #we accept all of this bid and keep going
                            bid.accepted = True
                            self.STPlan.addBid(bid)
                    else:
                        #we have enough power already, decline remaining bids
                        bid.accepted = False
                
                #notify the counterparties of the terms on which they will supply power
            for bid in bidList:
                if bid.accepted:
                    sendBidAcceptance(bid, rate)
                else:
                    sendBidRejected(bid, rate)    
            # now book enough reserves to handle worst case         
            resupply = supply
            for bid in bidList:
                if bid.service == "reserve":
                    if resupply < maxLoad:
                        resupply += bid.amount
                        if supply > maxLoad:
                            #now we have enough reserves
                            bid.accepted = True
                            bid.modified = True
                            amount = bid.amount-(resupply-maxLoad)
                        else:
                            #need more 
                            bid.accepted = True
                    else:
                        bid.accepted = False
                else:
                    pass
                
            
            #not enough supply available to meet demand, we'll have to shed load or something
            if supply < expLoad:
                if settings.DEBUGGING_LEVEL >= 2:
                    print("UTILITY {me} IS EXPERIENCING A SUPPLY SHORTFALL IN GROUP {group}".format(me = self.name, group = group.name))
            
    def sendBidAcceptance(self,bid,rate):
        mesdict = {}
        mesdict["message_subject"] = "bid_acceptance"
        mesdict["message_target"] = bid.counterparty
        mesdict["message_sender"] = self.name
        
        mesdict["amount"] = bid.amount
        mesdict["service"] = bid.service
        mesdict["rate"] = rate        
        mesdict["period"] = bid.period
        mesdict["uid"] = bid.uid
        
        mess = json.dumps(mesdict)
    
    '''solicit participation in DR scheme from all customers who are not
    currently participants'''
    @Core.periodic(settings.DR_SOLICITATION_INTERVAL)
    def DREnrollment(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY {me} TRYING TO ENROLL CUSTOMERS IN A DR SCHEME".format(me = self.name))
        for entry in self.customers:
            if entry.DRenrollee == False:
                self.solicitDREnrollment(entry.name)
    
    '''broadcast message in search of new customers'''
    @Core.periodic(settings.CUSTOMER_SOLICITATION_INTERVAL)
    def discoverCustomers(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY {me} TRYING TO FIND CUSTOMERS".format(me = self.name))
        mesdict = self.standardCustomerEnrollment
        mesdict["message_sender"] = self.name
        message = json.dumps(mesdict)
        self.vip.pubsub.publish(peer = "pubsub", topic = "customerservice", headers = {}, message = message)
        
        if settings.DEBUGGING_LEVEL >= 1:
            print(message)
            
    '''move into the next planning period'''        
    @Core.periodic(settings.ST_PLAN_INTERVAL)
    def nextPeriod(self):
        self.STPinterval += 1
        #execute corresponding plan
    
    '''find out how much power is available from utility owned resources for a group at the moment'''    
    def getAvailableGroupPower(self,group):
        #first check to see what the grid topology is
        total = 0
        for elem in group.resources:
            if elem is SolarPanel:
                total += elem.maxDischargePower*self.perceivedInsol/100
            elif elem is LeadAcidBattery:
                if elem.SOC < .2:
                    total += 0
                elif elem.SOC > .4:
                    total += 20
            else:
                pass
        return total
    
            
    def getAvailableGroupDR(self,group):
        pass
    
    def getMaxGroupLoad(self,group):
        total = 0
        for load in group.resources:
            total += group.resources.maxDraw
        return total
    
    def getCurrentMarginalCost(self):
        pass
    
    
    '''update agent's knowledge of the current grid topology'''
    def getTopology(self):
        self.rebuildConnMatrix()
        subs = graph.findDisjointSubgraphs(self.connMatrix)
        if len(subs) >= 1:
            self.groupList = []
            for i in range(1,len(subs)+1):
                #create a new group class for each disjoint subgraph
                self.groupList.append(groups.Group("group{i}".format(i = i)))            
            for index,sub in enumerate(subs):
                #for concision
                cGroup = self.groupList[index]
                for node in sub:
                    #for concision
                    cNode = self.nodes[node]
                    #update the node's membership field to indicate which group it belongs to
                    cNode.membership = self.groupList[index].name
                    #add the node to the group's membership array
                    cGroup.membership.append(cNode)
                    #add the node's resources to the group's resource array
                    cGroup.resources.extend(cNode.resources)
                    
        else:
            print("got a weird number of disjoint subgraphs in utilityagent.getTopology()")
        return subs
    
    '''builds the connectivity matrix for the grid's infrastructure'''
    def rebuildConnMatrix(self):
        pass
    
    def marketfeed(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get("message_subject",None)
        messageTarget = mesdict.get("message_target",None)
        messageSender = mesdict.get("message_sender",None)
        
        if listparse.isRecipient(messageTarget,self.name):
            if messageSubject == "bid_response":
                service = mesdict.get("service",None)
                rate =  mesdict.get("rate",None)
                power = mesdict.get("power",None)
                duration = mesdict.get("power",None)
                amount = mesdict.get("amount",None)
                period = mesdict.get("period",None)
                uid = mesdict.get("uid",None)
                
                if settings.DEBUGGING_LEVEL >= 1:
                    print("UTILITY {me} RECEIVED A BID#{id} FROM {them}".format(me = self.name, id = self.uid, them = messageSender ))
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("    MESSAGE: {mes}".format(mes = message))
                    
                self.bidList.append(financial.Bid(service,amount,rate,messageSender,period,uid))
                
    '''callback for demandresponse topic'''
    def DRfeed(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get("message_subject",None)
        messageTarget = mesdict.get("message_target",None)
        messageSender = mesdict.get("message_sender",None)
        if listparse.isRecipient(messageTarget,self.name):
            if messageSubject == "DR_enrollment":
                messageType = mesdict.get("message_type",None)
                if messageType == "enrollment_reply":
                    if mesdict.get("opt_in"):
                        custobject = self.lookUpByName(messageSender,self.customers)
                        self.DRparticipants.append(custobject)
                        
                        resdict = {}
                        resdict["message_target"] = messageSender
                        resdict["message_subject"] = "DR_enrollment"
                        resdict["message_type"] = "enrollment_confirm"
                        resdict["message_sender"] = self.name
                        
                        response = json.dumps(resdict)
                        self.vip.pubsub.publish("pubsub","demandresponse",{},response)
                        
                        if settings.DEBUGGING_LEVEL >= 1:
                            print("ENROLLMENT SUCCESSFUL! {me} enrolled {them} in DR scheme".format(me = self.name, them = messageSender))
                            print(self.DRparticipants)
                            
    '''helper function to get the name of a resource or customer from a list of
    class objects'''                        
    def lookUpByName(self,name,list):
        for customer in list:
            if customer.name == name:
                return customer
    
    def printInfo(self,verbosity):
        print("~~SUMMARY OF UTILITY KNOWLEDGE~~")
        print("UTILITY NAME: {name}".format(name = self.name))
        
        print("--LIST ALL {n} UTILITY OWNED RESOURCES------".format(n = len(self.Resources)))
        for res in self.Resources:
            res.printInfo()
        print("--LIST ALL {n} CUSTOMERS----------------".format(n=len(self.customers)))
        for cust in self.customers:
            cust.printInfo()
        if verbosity > 1:
            print("--LIST ALL {n} DR PARTICIPANTS----------".format(n = len(self.DRparticipants)))
            for part in self.DRparticipants:
                part.printInfo()
            print("--THERE ARE {n} GROUPS------------------".format(n = len(self.groupList)))
            for group in self.groupList:
                print("    {name} INCLUDES THE FOLLOWING CUSTOMERS:".format(name = group.name))
                for cust in group.customers:
                    cust.printInfo()
                for res in group.resources:
                    res.printInfo()
                    
    
    def closeInfRelay(self,rname):
        tagClient.writeTags([rname],[False])
        
    def openInfRelay(self,rname):
        tagClient.writeTags([rname],[True])
        
        
def main(argv = sys.argv):
    try:
        utils.vip_main(UtilityAgent)
    except Exception as e:
        _log.exception('unhandled exception')
        
if __name__ == '__main__':
    sys.exit(main())
    
