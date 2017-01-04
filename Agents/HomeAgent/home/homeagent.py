from __future__ import absolute_import
from datetime import datetime, timedelta
import logging
import sys
import json

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from DCMGClasses.CIP import wrapper
from DCMGClasses.resources.misc import listparse
from DCMGClasses.resources.math import interpolation
from DCMGClasses.resources import resource, customer


from . import settings
utils.setup_logging()
_log = logging.getLogger(__name__)

class HomeAgent(Agent):
    
    
    def __init__(self,config_path,**kwargs):
        super(HomeAgent,self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config['agentid']
        #read from config structure
        self.name = self.config["name"]
        self.location = self.config["location"]
        self.resources = self.config["resources"]
        self.demandCurve = self.config["demandCurve"]
        
        self.Resources = []
        
        loclist = self.location.split('.')
        if type(loclist) is list:
            if loclist[0] == "DC":
                self.grid, self.branch, self.bus, self.load = loclist
            elif loclist[0] == "AC":
                pass
            else:
                print("the first part of the location path should be AC or DC")
        
        #create resource objects for resources
        resource.addResource(self.resources,self.Resources,True)
        
                    
        self.DR_participant = False
        self.gridConnected = False
        self.registered = False
        
        
    @Core.receiver('onstart')
    def setup(self,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        print('!!!Hello!!! Agent for the {name} home at {loc} starting up'.format(name = self.name, loc = self.location))
        
        self.vip.pubsub.subscribe('pubsub','energymarket', callback = self.followmarket)
        self.vip.pubsub.subscribe('pubsub','demandresponse',callback = self.DRfeed)
        self.vip.pubsub.subscribe('pubsub','customerservice',callback = self.customerfeed)
        self.vip.pubsub.subscribe('pubsub','weatherservice',callback = self.weatherfeed)
    
    '''callback for customerservice topic'''    
    def customerfeed(self, peer, sender, bus, topic, headers, message):
        print("customerfeed->home")
        mesdict = json.loads(message)
        messageTarget = mesdict.get("message_target",None)        
        if listparse.isRecipient(messageTarget,self.name, True):  
            messageSubject = mesdict.get("message_subject",None)
            messageType = mesdict.get("message_type",None)
            messageSender = mesdict.get("message_sender",None)
            if settings.DEBUGGING_LEVEL >= 2:
                print("{name} home agent received: {mes}".format(name = self.name, mes = message))
                
            if messageSubject == "customer_enrollment":
                if messageType == "new_customer_query":
                    rereg = mesdict.get("rereg",False)
                    if self.registered == False or rereg == True:
                        resdict = {}
                        resdict["message_subject"] = "customer_enrollment"
                        resdict["message_type"] = "new_customer_response"
                        resdict["message_target"] = messageSender
                        resdict["message_sender"] = self.name
                        resdict["info"] = [self.name, self.location, self.resources, "residential"]
                        
                        response = json.dumps(resdict)
                        self.vip.pubsub.publish(peer = "pubsub", topic = "customerservice", headers = {}, message = response)
                                                
                        if settings.DEBUGGING_LEVEL >= 1:
                            print("responding to enrollment request: {res}".format(res = response))
                    else:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("{me} ignoring enrollment request, already enrolled".format(me = self.name))
                elif messageType == "new_customer_confirm":
                    self.registered = True
                    
    def priceChange(self,newPrice):
        newdemand = interpolation.lininterp(self.demandCurve,newPrice)
        if newDemand == 0:
            self.disconnectLoad()
            print("{name} has attempted to disconnect from the grid".format(name = self.name))
        else:
            if self.gridConnected:
                pass
            else:
                self.connectLoad()
                print("{name} has attempted to connect to the grid".format(name = self.name))
        
    def followmarket(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        
        messageSubject = mesdict.get('message_subject',None)
        messageTarget = mesdict.get('message_target',None)
        
        if settings.DEBUGGING_LEVEL >= 2:
            print("{name} received a {top} message: {sub}".format(name = self.name, top = topic, sub = messageSubject))
        
        if listparse.isRecipient(messageTarget,self.name):
            if messageSubject == 'bid_solicitation':
                if len(self.resources) != 0:                
                    self.generate_bid()
                else:
                    return 0
            elif messageSubject == 'bid_response':
                #if acceptable, we'll have to follow through
                pass
            elif messageSubject == "spot_update":
                self.energySpot = mesdict.get("new_spot")
                priceChanged(self.energySpot)
                
        
                
    def DRfeed(self,peer,sender,bus,topic,headers,message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get('message_subject',None)
        messageTarget = mesdict.get('message_target',None)
        messageSender = mesdict.get("message_sender",None)
        if listparse.isRecipient(messageTarget,self.name):
            print("{name} home agent has received a DRfeed message".format(name = self.name))
            if messageSubject == 'DR_event':
                # if enrolled, we have to act on the request
                eventType = mesdict.get('event_type',None)
                eventID = mesdict.get('event_id',None)
                response = {}
                response["message_subject"] = "DR_event"
                response["message_target"] = messageSender
                response["event_id"] = eventID
                if self.DR_participant == True:
                    if eventType == 'normal':
                        changeConsumption(1)
                    elif eventType == 'grid_emergency':
                        changeConsumption(0)
                    elif eventType == 'shed':
                        changeConsumption(0)
                    elif eventType == 'critical_peak':
                        changeConsumption(0)
                    elif eventType == 'load_up':
                        changeConsumption(1)
                    else:
                        print('got a weird demand response eventType')
                    
                    response["opt_in"] = True
                else:
                    response["opt_in"] = False
                    
                mes = json.dumps(response)
                self.vip.pubsub.publish("pubsub","demandresponse",{},mes)
                    
            elif messageSubject == 'DR_enrollment':
                type = mesdict.get("message_type")
                if type == "enrollment_query":
                    if self.DR_participant == False:
                        response = {}
                        response["message_target"] = messageSender
                        response["message_subject"] = "DR_enrollment"
                        response["message_type"] = "enrollment_reply"
                        response["message_sender"] = self.name
                        response["opt_in"] = True
                        #response["payload"] = False
                        
                        mes = json.dumps(response)
                        self.vip.pubsub.publish("pubsub","demandresponse",{},mes)
                        
                        if settings.DEBUGGING_LEVEL >= 1:
                            print("{me} opted in to DR program".format(me = self.name), )
                    
                elif type == "enrollment_confirm":
                    self.DR_participant = True    
                    
    @Core.periodic(settings.REASSESS_INTERVAL)
    def reassess_utility(self):
        pass
    
    def generate_bid(self):
        bid = {}
        service = None
        price = 0 
        power = 0
        duration = 0
        
        for source in self.resources:
            if isinstance(source,Source):
                if isinstance(source,SolarPanel):
                    pass
            elif isinstance(source,Storage):
                if isinstance(source,LeadAcidBattery):
                    service = "voltage_regulation"
                    price = 2
                    power = 10
                    duration = 120
                
                
        
        bid['service'] = service
        bid['price'] = price
        bid['power'] = power
        bid['duration'] = duration
        
    def changeConsumption(self, level):
        if level == 0:
            self.disconnectLoad()
        elif level == 1:
            self.connectLoad()
        else:
            pass
    
    def disconnectLoad(self):
        #this is where we'll call the CIP stack wrapper to disconnect load
        tagName = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_User".format(branch = self.branch, bus = self.bus, load = self.load)
        setTagValue(tagName,False)
    
    def connectLoad(self):
        #this is where we'll call the CIP stack wrapper to connect load
        tagName = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_User".format(branch = self.branch, bus = self.bus, load = self.load)
        setTagValue(tagName,True)
    
def main(argv = sys.argv):
    '''Main method called by the eggseccutable'''
    try:
        utils.vip_main(HomeAgent)
    except Exception as e:
        _log.exception('unhandled exception')
        
if __name__ == '__main__':
    sys.exit(main())