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
from DCMGClasses.resources import resource


from . import settings
utils.setup_logging()
_log = logging.getLogger(__name__)

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
        self._agent_id = self.config['agent_id']
        
        
        self.name = self.config["name"]
        
        
        self.customers = []
        
    @Core.receiver('onstart')
    def setup(selfself,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        self.vip.pubsub.subscribe('pubsub','energymarket', callback = self.marketfeed)
        self.vip.pubsub.subscribe('pubsub','demandresponse',callback = self.DRfeed)
        self.vip.pubsub.subscribe('pubsub','customerservice',callback = self.customerfeed)
        
        if settings.DEBUGGING_LEVEL >= 1:
            print("utility agent {name} trying to discover customers".format(name = self.name))
        self.discoverCustomers()
        
    def customerfeed(self, peer, sender, bus, topic, headers, message):
        try:
            mesdict = json.loads(message)
        except Exception as e:
            print("customerfeed message to {me} was not formatted properly".format(me = self))
            
        messageTarget = mesdict.get("message_target",None)
        if isRecipient(messageTarget,self.name):
            messageSubject = mesdict.get("message_subject",None)
            messageType = mesdict.get("message_type",None)
            if messageSubject == "customer_enrollment":
                if messageType == "new_customer_response":
                    try:
                        name, location, resources, customerType = mesdict.get("info")                        
                    except Exception as e:
                        print("customer information improperly formatted :(")
                        
                    if customerType == "residential":
                        self.customers.append(ResidentialCustomerProfile(name,location,resources))
                    elif customerType == "commercial":
                        self.customers.append(CommercialCustomerProfile(name,location,resources))
                    else:
                        pass
                    
                    if settings.DEBUGGING_LEVEL >= 1:
                        print("customer_enrolled! {mes}".format(mes = message))
                        print(self.customers)
                
            else:
                pass
        pass
        
    def solicitDREnrollment(self, name = "broadcast"):
        mesdict = {}
        mesdict["message_subject"] = "DR_enrollment"
        mesdict["message_type"] = "enrollment_query"
        mesdict["message_target"] = name
        mesdict["info"] = "name"
        
        message = json.dumps(mesdict)
        self.vip.pubsub.publish(peer = "pubsub", topic = "demandresponse", headers = {}, message = message)
        if DEBUGGING_LEVEL >= 1:
            print("{name} is trying to enroll DR participants: {mes}".format(name = self.name, mes = message))
    
    @Core.periodic(settings.LT_PLAN_INTERVAL)
    def planLongTerm(self):
        pass
    
    @Core.periodic(settings.ST_PLAN_INTERVAL)
    def planShortTerm(self):
        pass
    
    @Core.periodic(settings.DR_SOLICITATION_INTERVAL)
    def solicitDREnrollment(self):
        for entry in customers:
            if entry.DRenrollee == False:
                solicitDREnrollment(entry.name)
    
    @Core.periodic(settings.CUSTOMER_SOLICITATION_INTERVAL)
    def discoverCustomers(self):
        message = json.dumps(self.standardCustomerEnrollment)
        self.vip.pubsub.publish(peer = "pubsub", topic = "customerservice", headers = {}, message = message)
    
    def marketfeed(self, peer, sender, bus, topic, headers, message):
        pass
    
    def DRfeed(self, peer, sender, bus, topic, headers, message):
        pass
        