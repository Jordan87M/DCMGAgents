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
        
        loclist = self.location.strsplit('.')
        if type(loclist) is list:
            if loclist(0) == "DC":
                self.grid, self.branch, self.bus, self.load = loclist
            elif loclist(0) == "AC":
                pass
            else:
                print("the first part of the location path should be AC or DC")
        

        self.DR_participant = False
        self.gridConnected = False
        
        
    @Core.receiver('onstart')
    def setup(self,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        print('!!!Hello!!! Agent for the {name} home at {loc} starting up'.format(name = self.name, loc = self.location))
        
        self.vip.pubsub.subscribe('pubsub','energymarket', callback = self.followmarket)
        self.vip.pubsub.subscribe('pubsub','demandresponse',callback = self.DRfeed)
        
    def priceChange(self,newPrice):
        newdemand = lininterp(self.demandCurve,newPrice)
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
        if isRecipient(messageTarget,self.name):
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
        if isRecipient(messageTarget,self.name):
            if messageSubject == 'DR_event':
                # if enrolled, we have to act on the request
                severity = mesdict.get('message_subject',None)
                eventID = mesdict.get('event_id',None)
                if DR_participant == True:
                    if severity == 'normal':
                        changeConsumption(1)
                    elif severity == 'grid_emergency':
                        changeConsumption(0)
                    elif severity == 'shed':
                        changeConsumption(0)
                    elif severity == 'critical_peak':
                        changeConsumption(0)
                    elif severity == 'load_up':
                        changeConsumption(1)
                    else:
                        print('got a weird demand response severity')
                    response = {}
                    response["messge_subject"] = "DR_event"
                    response["event_id"] = eventID
                    response["opt_in"] = True
                else:
                    response = {}
                    response["message_subject"] = "DR_event"
                    response["event_id"] = eventID
                    response["opt_in"] = False
                    
                mes = json.dumps(response)
                self.vip.pubsub.publish("pubsub","demandresponse",{},mes)
                    
            elif messageSubject == 'DR_enrollment':
                type = mesdict.get("message_type")
                if type == "enrollment_query":
                    response = {}
                    response["message_subject"] = "DR_enrollment"
                    response["message_type"] = "enrollment_reply"
                    response["payload"] = "IN"
                    #response["payload"] = "OUT"
                    
                    mes = json.dumps(ctadict)
                    self.vip.pubsub.publish("pubsub","demandresponse",{},mes)
                
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
        setTagValue(tagName,False))
    
    def connectLoad(self):
        #this is where we'll call the CIP stack wrapper to connect load
        tagName = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_User".format(branch = self.branch, bus = self.bus, load = self.load)
        setTagValue(tagName,True))
    
def main(argv = sys.argv):
    '''Main method called by the eggseccutable'''
    try:
        utils.vip_main(HomeAgent)
    except Exception as e:
        _log.exception('unhandled exception')
        
if __name__ == '__main__':
    sys.exit(main())