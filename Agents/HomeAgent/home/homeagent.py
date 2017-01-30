from __future__ import absolute_import
from datetime import datetime, timedelta
import logging
import sys
import json
import random

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from DCMGClasses.CIP import tagClient
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
        self.perceivedInsol = 10
        #the following variables 
        self.FREGpart = bool(self.config["FREGpart"])
        self.DRpart = bool(self.config["DRpart"])
        
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
        self.FREG_participant = False
        self.gridConnected = False
        self.registered = False
        
        self.avgEnergyCost = 1
        self.outstandingBids = []
        
        start = datetime.now()
        #this value doesn't matter
        end = start + timedelta(seconds = 30)
        self.CurrentPeriod = control.Period(0,start,end,self.name)
        self.NextPeriod = control.Period(0,start,end,self.name)
        
    @Core.receiver('onstart')
    def setup(self,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        print('!!!Hello!!! Agent for the {name} home at {loc} starting up'.format(name = self.name, loc = self.location))
        
        self.vip.pubsub.subscribe('pubsub','energymarket', callback = self.followmarket)
        self.vip.pubsub.subscribe('pubsub','demandresponse',callback = self.DRfeed)
        self.vip.pubsub.subscribe('pubsub','customerservice',callback = self.customerfeed)
        self.vip.pubsub.subscribe('pubsub','weatherservice',callback = self.weatherfeed)
        self.vip.pubsub.subscribe("pubsub","FREG",callback = self.FREGfeed)
        
        self.printInfo(1)
        
    '''callback for frequency regulation signal topic'''
    def FREGfeed(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        messageTarget = mesdict.get("message_target",None)
        messageSubject = mesdict.get("message_subject",None)
        messageSender = mesdict.get("message_sender",None)
        # if the message is meant for us
        if listparse.isRecipient(messageTarget,self.name,False):
            if messageSubject == "FREG_enrollment":
                messageType = mesdict.get("message_type",None)
                #if message is solicitation, sign up or ignore
                if messageType == "solicitation":
                    if self.FREGpart:
                        FREG_report = 0
                        for res in self.Resources:
                            if res is resource.LeadAcidBattery:
                                res.FREG_power = .2 * res.maxDischargePower
                                FREG_report += res.FREG_power
                        resdict = {"message_subject" : "FREG_enrollment",
                                   "message_sender" : self.name,
                                   "message_target" : messageSender,
                                   "message_type" : "acceptance",
                                   "FREG_power" : FREG_report
                                   }
                        response = json.dumps(resdict)
                        self.vip.pubsub.publish("pubsub","FREG",{},response)
                #message is an ACK, consider ourselves an enrollee
                elif messageType == "enrollment_ACK":
                    self.FREG_participant == True
            if messageSubject == "FREG_signal":
                #if we are a participant, and we are able, follow the FREG signal
                if self.FREG_participant:
                    sig = mesdict.get("FREG_signal",None)
                    if sig <= 1 and sig > 0:
                        for res in self.Resources:
                            #stop any batteries that may be charging
                            if res is resources.LeadAcidBattery:
                                if res.ChargeChannel.connected == True:
                                    res.ChargeChannel.disconnect()
                                    
                            #is extra power available?
                            avail = res.availDischargePower
                            current = res.getOutputRegPower()
                            headroom = avail - current
                            poffset = res.FREG_power*sig
                            if poffset > headroom:
                                poffset = headroom
                                
                            #if resource is already connected, adjust power offset
                            if headroom > .1:
                                if resource.DischargeChannel.connected:
                                    res.DischargeChannel.setPowerOffset(poffset)
                                else:
                                    res.DischargeChannel.connectWithSet(poffset,0)   
                    elif sig == 0:
                        for res in self.Resources:
                            #stop any batteries that may be charging
                            if res is resources.LeadAcidBattery:
                                if res.ChargeChannel.connected == True:
                                    res.ChargeChannel.disconnect()
                             #if resource is already connected, adjust power offset                            
                            if resource.DischargeChannel.connected:
                                res.DischargeChannel.setPowerOffset(0)
                                
                                                                                    
                    elif sig < 0 and sig >= -1:
                        for res in self.Resources:
                            #charge a battery if available
                            if res is resources.LeadAcidBattery:
                                if res.SOC < 95:
                                    res.charge(sig*self.FREG_power)
                                    if settings.DEBUGGING_LEVEL >= 2:
                                        print("STORAGE DEVICE {me}: charging at {rate} W".format(me = self.name, rate = sig*self.FREG_power))
                                else:
                                    if settings.DEBUGGING_LEVEL >= 2:
                                        print("STORAGE DEVICE {me}: SOC {soc} is too high to charge".format(me = self.name, soc = res.SOC))
                    
        
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
                            print("\nHOME {me} responding to enrollment request: {res}".format(me = self.name, res = response))
                    else:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("\nHOME {me} ignoring enrollment request, already enrolled".format(me = self.name))
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
        
                
        if listparse.isRecipient(messageTarget,self.name):
            if settings.DEBUGGING_LEVEL >= 2:
                print("\nHOME {name} received a {top} message: {sub}".format(name = self.name, top = topic, sub = messageSubject))
                #print(message)
            #sent by a utility agent to elicit bids for generation    
            if messageSubject == 'bid_solicitation':
                service = mesdict.get("service",None)
                period = mesdict.get("period",None)
                counterparty = messageSender
                if self.Resources:
                    biddict = {}
                    biddict["message_subject"] = "bid_response"
                    biddict["message_target"] = messageSender
                    biddict["message_sender"] = self.name
        
                    for res in self.Resources:
                        if type(res) is resource.SolarPanel:
                            amount = res.maxDischargePower*self.perceivedInsol/100
                            rate = financial.ratecalc(res.capCost,.05,res.amortizationPeriod,.2)
                            biddict["amount"] = amount
                            biddict["service"] = service
                            biddict["rate"] = rate
                            biddict["counterparty"] = counterparty
                            biddict["duration"] = 1
                            biddict["period"] = period
                            biddict["resource"] = res.name
                            #add to local list of outstanding bids
                            newBid = financial.Bid(res.name,service,amount,rate,counterparty,period)
                            self.outstandingBids.append(newBid)
                            biddict["uid"] = newBid.uid
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("\nHOME AGENT {me} ADDED AN OUTSTANDING BID".format(me = self.name))
                                print("HERE'S THE LIST OF OUTSTANDING BIDS:")
                                for bid in self.outstandingBids:
                                    bid.printInfo()
                                    
                            #and send to utility for consideration
                            mess = json.dumps(biddict)
                            self.vip.pubsub.publish(peer = "pubsub",topic = "energymarket",headers = {}, message = mess)
                            
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("\nNEW BID TENDERED BY {me}".format(me = self.name))
                                newBid.printInfo()
                            
                        elif type(res) is resource.LeadAcidBattery:
                            if res.SOC > .2:
                                amount = 10
                                rate = max(financial.ratecalc(res.capCost,.05,res.amortizationPeriod,.05),self.capCost/self.cyclelife) + self.avgEnergyCost*amount
                                bid["amount"] = amount
                                bid["service"] = service
                                bid["rate"] = rate
                                bid["counterparty"] = counterparty
                                bid["duration"] = 1
                                bid["period"] = period
                                bid["resource"] = res.name
                                
                                newBid = financial.Bid(res.name,service,amount,rate,counterparty,period)
                                self.outstandingBids.append(newBid)
                                
                                if settings.DEBUGGING_LEVEL >= 2:
                                    print("\nHOME AGENT {me} ADDED AN OUTSTANDING BID".format(me = self.name))
                                    print("HERE'S THE LIST OF OUTSTANDING BIDS:")
                                    for bid in self.outstandingBids:
                                        bid.printInfo()
                                    
                                mess = json.dumps(bid)
                                self.vip.pubsub.publish(peer = "pubsub",topic = "energymarket",headers = {}, message = mess)
                                
                                if settings.DEBUGGING_LEVEL >= 2:
                                    print("\nNEW BID TENDERED BY {me}".format(me = self.name))
                                    newBid.printInfo()
                        else:
                            print("A PROBLEM: {type} is not a recognized type".format(type = type(res)))
            #received when a homeowner's bid has been accepted    
            elif messageSubject == 'bid_acceptance':
                #if acceptable, update the plan
                
                service = mesdict.get("service",None)
                amount = mesdict.get("amount",None)
                rate = mesdict.get("rate",None)
                period = mesdict.get("period",None)
                uid = mesdict.get("uid",None)
                
                #amount or rate may have been changed
                #service also may have been changed from power to regulation
                for bid in self.outstandingBids:
                    print("HOME AGENT {me} COMPARING REC:{rec}|STORED:{sto}".format(me = self.name, rec = uid, sto = bid.uid))
                    if bid.uid == uid:
                        bid.service = service
                        bid.amount = amount
                        bid.rate = rate
                        bid.period = period
                        if bid.period == self.NextPeriod.periodNumber:
                            self.NextPeriod.actionPlan.addBid(bid)
                            self.outstandingBids.remove(bid)
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("\n-->HOMEOWNER {me} ACK BID ACCEPTANCE".format(me = self.name))
                            bid.printInfo()
                
            elif messageSubject == "bid_rejection":
                #if the bid is not accepted, just remove the bid from the list of outstanding bids
                uid = mesdict.get("uid",None)
                for bid in self.outstandingBids:
                    if bid.uid == uid:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("\n-->HOMEOWNER {me} ACK BID REJECTION".format(me = self.name))
                            bid.printInfo()
                        self.outstandingBids.remove(bid)
            #subject used for handling general announcements            
            elif messageSubject == "announcement":
                messageType = mesdict.get("message_type",None)
                #announcement of next period start and stop times to ensure synchronization
                if messageType == "next_period_time":
                    period = mesdict.get("period_number",None)
                    #if this is a period we don't know about, it should be a new one
                    if period > self.NextPeriod.periodNumber:
                        startTime = mesdict.get("start_time",None)
                        endTime = mesdict.get("end_time",None)
                        startdtime = datetime.strptime(startTime,"%Y-%m-%dT%H:%M:%S.%f")
                        enddtime = datetime.strptime(endTime,"%Y-%m-%dT%H:%M:%S.%f")
                        self.NextPeriod = control.Period(period,startdtime,enddtime,self.name)
                        #schedule a callback to begin the new period
                        self.core.schedule(startdtime,self.advancePeriod)
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
                        self.changeConsumption(1)
                    elif eventType == 'grid_emergency':
                        self.changeConsumption(0)
                    elif eventType == 'shed':
                        self.changeConsumption(0)
                    elif eventType == 'critical_peak':
                        self.changeConsumption(0)
                    elif eventType == 'load_up':
                        self.changeConsumption(1)
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
                            print("\nHOME {me} opted in to DR program".format(me = self.name), )
                    
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
    
    def advancePeriod(self):
        self.CurrentPeriod = self.NextPeriod
        #contra the utility version of this fn, don't create the next period
        
        if settings.DEBUGGING_LEVEL >= 1:
            print("\nHOMEOWNER AGENT {me} moving into new period:".format(me = self.name))
            self.CurrentPeriod.printInfo()
        
        #call enact plan
        self.enactPlan()
        
        #also don't schedule next call, wait for announcement from utility
    
    '''responsible for enacting the plan which has been defined for a planning period'''
    def enactPlan(self):
        #all changes in setpoints should be made gradually, i.e. by using
        #resource.connectSoft() or resource.ramp()
        
        #involvedResources will help figure out which resources must be disconnected
        involvedResources = []
        #change setpoints
        if self.CurrentPeriod.actionPlan:
            for bid in self.CurrentPeriod.actionPlan.ownBids:
                res = listparse.lookUpByName(bid.resourceName)
                involvedResources.append(res)
                #if the resource is already connected, change the setpoint
                if res.connected == True:
                    if bid.service == "power":
                        #res.DischargeChannel.ramp(bid.amount)
                        res.DischargeChannel.changeSetpoint(bid.amount)
                    elif bid.service == "reserve":
                        #res.DischargeChannel.ramp(.1)
                        res.DischargeChannel.changeReserve(bid.amount,-.4)
                #if the resource isn't connected, connect it and ramp up power
                else:
                    if bid.service == "power":
                        #res.connectSourceSoft("Preg",bid.amount)
                        res.DischargeChannel.connectWithSet(bid.amount,0 )
                    elif bid.servie == "reserve":
                        #res.connectSourceSoft("Preg",.1)
                        res.DischargeChannel.connectWithSet(bid.amount, -.4)
            #ramp down and disconnect resources that aren't being used anymore
            for res in self.Resources:
                if res not in involvedResources:
                    if res.connected == True:
                        #res.disconnectSourceSoft()
                        res.DischargeChannel.disconnect()
    
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