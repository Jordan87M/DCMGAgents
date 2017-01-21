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
from DCMGClasses.resources import resource, customer, control, financial


from . import settings
from zmq.backend.cython.constants import RATE
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
        self.perceivedInsol = 0
        
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
        
        self.avgEnergyCost = 1
        self.cPlan = control.Plan(self,1)
        self.outstandingBids = []
        
    @Core.receiver('onstart')
    def setup(self,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        print('!!!Hello!!! Agent for the {name} home at {loc} starting up'.format(name = self.name, loc = self.location))
        
        self.vip.pubsub.subscribe('pubsub','energymarket', callback = self.followmarket)
        self.vip.pubsub.subscribe('pubsub','demandresponse',callback = self.DRfeed)
        self.vip.pubsub.subscribe('pubsub','customerservice',callback = self.customerfeed)
        self.vip.pubsub.subscribe('pubsub','weatherservice',callback = self.weatherfeed)
        
        self.printInfo(1)
        
    '''callback for customerservice topic'''    
    def customerfeed(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        messageTarget = mesdict.get("message_target",None)        
        if listparse.isRecipient(messageTarget,self.name, False):  
            messageSubject = mesdict.get("message_subject",None)
            messageType = mesdict.get("message_type",None)
            messageSender = mesdict.get("message_sender",None)
            
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
                            print("HOME {me} responding to enrollment request: {res}".format(me = self.name, res = response))
                    else:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("HOME {me} ignoring enrollment request, already enrolled".format(me = self.name))
                elif messageType == "new_customer_confirm":
                    self.registered = True
                    
    def priceChange(self,newPrice):
        newdemand = interpolation.lininterp(self.demandCurve,newPrice)
        if newDemand == 0:
            self.disconnectLoad()
            print("HOME {name} has attempted to disconnect from the grid".format(name = self.name))
        else:
            if self.gridConnected:
                pass
            else:
                self.connectLoad()
                print("HOME {name} has attempted to connect to the grid".format(name = self.name))
        
    def followmarket(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        
        messageSubject = mesdict.get('message_subject',None)
        messageSender = mesdict.get("message_sender",None)
        messageTarget = mesdict.get('message_target',None)
        
        if settings.DEBUGGING_LEVEL >= 2:
            print("HOME {name} received a {top} message: {sub}".format(name = self.name, top = topic, sub = messageSubject))
        
        if listparse.isRecipient(messageTarget,self.name):
            if messageSubject == 'bid_solicitation':
                service = mesdict.get("service",None)
                service = mesdict.get("period",None)
                counterparty = messageSender
                if self.resources:
                    bid = {}
                    bid["message_subject"] = "bid_response"
                    bid["message_target"] = "message_sender"
                    bid["message_sender"] = self.name
        
                    for res in self.Resources:
                        if type(res) is resource.SolarPanel:
                            amount = res.maxDischargePower*self.perceivedInsol/100
                            rate = financial.ratecalc(res.capCost,.05,res.amortizationPeriod,.2)
                        elif type(res) is resource.LeadAcidBattery:
                            amount = 10
                            rate = max(financial.ratecalc(res.capCost,.05,res.amortizationPeriod,.05),self.capCost/self.cyclelife) + self.avgEnergyCost*amount
                        else:
                            print("A PROBLEM: {type} is not a recognized type".format(type = type(res)))
                        bid["amount"] = amount
                        bid["service"] = service
                        bid["rate"] = rate
                        bid["counterparty"] = counterparty
                        bid["duration"] = 1
                        bid["period"] = period
                        
                        
                        self.outstandingBids.append(financial.Bid(service,amount,rate,counterparty,period))
                        
                        mess = json.dumps(bid)
                        if settings.DEBUGGING_LEVEL >= 1:
                            print("HOME {me} HAS HAD A BID FOR {service} ACCEPTED".format(me = self.name, service = service))
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("    MESSAGE: {mes}".format(mes = mess))
                        self.vip.publish.publish(peer = "pubsub",topic = "energymarket",headers = {}, message = mess)
        
            elif messageSubject == 'bid_acceptance':
                #if acceptable, update the plan
                
                service = mesdict.get("service",None)
                amount = mesdict.get("amount",None)
                rate = mesdict.get("rate",None)
                period = mesdict.get("period")
                uid = mesdict.get("uid")
                
                #amount or rate may have been changed
                #service also may have been changed from power to regulation
                for bid in outstandingBids:
                    if bid.uid == uid:
                        bid.service = service
                        bid.amount = amount
                        bid.rate = rate
                        bid.period = period
                                        
                        self.cPlan.addBid(bid)
                
            elif messageSubject == "bid_rejection":
                #if the bid is not accepted, just remove the bid from the list of outstanding bids
                uid = mesdict.get("uid")
                for bid in self.outstandingBids:
                    if bid.uid == uid:
                        self.outstandingBids.remove(bid)
                
            elif messageSubject == "spot_update":
                self.energySpot = mesdict.get("new_spot")
                priceChanged(self.energySpot)
                
    def weatherfeed(self,peer,sender,bus,topic,headers,message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get('message_subject',None)
        messageTarget = mesdict.get('message_target',None)
        messageSender = mesdict.get('message_sender',None)
        messageType = mesdict.get("message_type",None)
        
        if listparse.isRecipient(messageTarget,self.name):    
            if messageSubject == "nowcast":
                if messageType == "solar_irradiance":
                    self.perceivedInsol = mesdict.get("info",None)
                
    def DRfeed(self,peer,sender,bus,topic,headers,message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get('message_subject',None)
        messageTarget = mesdict.get('message_target',None)
        messageSender = mesdict.get("message_sender",None)
        if listparse.isRecipient(messageTarget,self.name):
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
                        
                        mes = json.dumps(response)
                        self.vip.pubsub.publish("pubsub","demandresponse",{},mes)
                        
                        if settings.DEBUGGING_LEVEL >= 1:
                            print("HOME {me} opted in to DR program".format(me = self.name), )
                    
                elif type == "enrollment_confirm":
                    self.DR_participant = True    
                    
    @Core.periodic(settings.REASSESS_INTERVAL)
    def reassess_utility(self):
        pass
    

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
        #setTagValue(tagName,False)
        tagClient.writeTags([tagName],[False])
    
    def connectLoad(self):
        #this is where we'll call the CIP stack wrapper to connect load
        tagName = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_User".format(branch = self.branch, bus = self.bus, load = self.load)
        #setTagValue(tagName,True)
        tagClient.writeTags([tagName],[True])
        
    def measureVoltage(self):
        tag = "BRANCH{branch}_BUS{bus}_LOAD{load}_Current".format(branch = self.branch, bus = self.bus, load = self.load)
        return tagClient.readTags([tag])
    
    def measureCurrent(self):
        tag = "BRANCH{branch}_BUS{bus}_LOAD{load}_Current".format(branch = self.branch, bus = self.bus, load = self.load)
        return tagClient.readTags([tag])
    
    def measurePower(self):
        return self.measureVoltage()*self.measureCurrent()
        
    def printInfo(self,verbosity):
        print("~~SUMMARY OF HOME STATE~~")
        print("HOME NAME: {name}".format(name = self.name))
        
        print("LIST ALL OWNED RESOURCES")
        for res in self.Resources:
            res.printInfo()
        
    
def main(argv = sys.argv):
    '''Main method called by the eggsecutable'''
    try:
        utils.vip_main(HomeAgent)
    except Exception as e:
        _log.exception('unhandled exception')
        
if __name__ == '__main__':
    sys.exit(main())