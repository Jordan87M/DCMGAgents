from __future__ import absolute_import
from datetime import datetime
import logging
import sys
import json

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from DCMGClasses.CIP import wrapper
from DCMGClasses.resources.misc import listparse
from DCMGClasses.resources.math import interpolation, graph
from DCMGClasses.resources import resource
from DCMGClasses.resources import customer


from . import settings
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
    
    
    def __init__(self,config_path,**kwargs):
        super(UtilityAgent,self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config['agentid']
        
        
        self.name = self.config["name"]
        self.resources = self.config["resources"]
        self.Resources = []
        
        resource.addResource(self.resources,self.Resources,True)
        
        self.customers = []
        self.DRparticipants = []
        
    @Core.receiver('onstart')
    def setup(self,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        self.vip.pubsub.subscribe('pubsub','energymarket', callback = self.marketfeed)
        self.vip.pubsub.subscribe('pubsub','demandresponse',callback = self.DRfeed)
        self.vip.pubsub.subscribe('pubsub','customerservice',callback = self.customerfeed)
        self.vip.pubsub.subscribe('pubsub','weatherservice',callback = self.weatherfeed)
        
        
        
        self.connMatrix = [[1,1,1,0,0],[1,1,0,1,0],[1,0,1,0,1],[0,1,0,1,0],[0,0,1,0,1]]
        self.groupMembership = {"DC.main": "maingroup",
                                "DC.BRANCH1.BUS1": "maingroup",
                                "DC.BRANCH1.BUS2": "maingroup",
                                "DC.BRANCH2.BUS1": "maingroup",
                                "DC.BRANCH2.BUS2": "maingroup"}
        self.nodeMap = {0:"DC.main",
                        1:"DC.BRANCH1.BUS1",
                        2:"DC.BRANCH1.BUS2",
                        3:"DC.BRANCH2.BUS1",
                        4:"DC.BRANCH2.BUS2"}
        
        if settings.DEBUGGING_LEVEL >= 1:
            print("utility agent {name} trying to discover customers".format(name = self.name))
        self.discoverCustomers()
    
    '''callback for weatherfeed topic'''
    def weatherfeed(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        
    
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
                        print("{me} received a customer enrollment response".format(me = self.name))
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
                            if len(resources) == 1:
                                addOneToPool(self.resourcePool,resources[0])                               
                        elif type(resources) is str or type(resources) is unicode:
                            addOneToPool(self.resourcePool,resources)
                    
                    if settings.DEBUGGING_LEVEL >= 1:
                        print("customer_enrolled! {mes}".format(mes = message))
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
            print("{name} is trying to enroll DR participants: {mes}".format(name = self.name, mes = message))
    
    
    @Core.periodic(settings.LT_PLAN_INTERVAL)
    def planLongTerm(self):
        pass
    
    @Core.periodic(settings.ST_PLAN_INTERVAL)
    def planShortTerm(self):
        pass
    
    '''solicit participation in DR scheme from all customers who are not
    currently participants'''
    @Core.periodic(settings.DR_SOLICITATION_INTERVAL)
    def DREnrollment(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("{me} trying to enroll customers in DR scheme".format(me = self.name))
        for entry in self.customers:
            if entry.DRenrollee == False:
                self.solicitDREnrollment(entry.name)
    
    '''broadcast message in search of new customers'''
    @Core.periodic(settings.CUSTOMER_SOLICITATION_INTERVAL)
    def discoverCustomers(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("{me} trying to find more customers".format(me = self.name))
        mesdict = self.standardCustomerEnrollment
        mesdict["message_sender"] = self.name
        message = json.dumps(mesdict)
        self.vip.pubsub.publish(peer = "pubsub", topic = "customerservice", headers = {}, message = message)
        
        if settings.DEBUGGING_LEVEL >= 1:
            print(message)
    
    '''find out how much power is available from utility owned resources at the moment'''    
    def getAvailablePower(self):
        #first check to see what the grid topology is
        total = 0
        for elem in self.Resources:
            if elem is SolarPanel:
                pass
            elif elem is LeadAcidBattery:
                if elem.SOC > .2:
                    contrib = 0
                elif elem.SOC > .4:
                    contrib = 20
                
                    
            else:
                pass
    
    def getCurrentMarginalCost(self):
        pass
    
    
    '''update agent's knowledge of the current grid topology'''
    def getTopology(self):
        self.rebuildConnMatrix()
        subs = findDisjointSubgraphs(self.connMatrix)
        if len(subs) == 1:
            #all nodes are connected
            for k in self.groupMembership:
                self.groupMembership[k] = "maingroup"
        elif len(subs) > 1:
            for index,group in enumerate(groups):
                for node in group:
                    k = self.nodeMap[node]
                    if index == 0:
                        self.groupMembership[k] ="maingroup"
                    else:
                        self.groupMembership[k] = "group{i}".format(i = index)
        else:
            print("got a weird number of disjoint subgraphs in utilityagent.getTopology()")
    
    '''builds the connectivity matrix for the grid's infrastructure'''
    def rebuildConnMatrix(self):
        pass
    
    def marketfeed(self, peer, sender, bus, topic, headers, message):
        pass
    
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
                            print("{me} enrolled {them} in DR scheme".format(me = self.name, them = messageSender))
                            print(self.DRparticipants)
                            
    '''helper function to get the name of a resource or customer from a list of
    class objects'''                        
    def lookUpByName(self,name,list):
        for customer in list:
            if customer.name == name:
                return customer
        
def main(argv = sys.argv):
    try:
        utils.vip_main(UtilityAgent)
    except Exception as e:
        _log.exception('unhandled exception')
        
if __name__ == '__main__':
    sys.exit(main())