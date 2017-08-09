from __future__ import absolute_import
from datetime import datetime, timedelta
import logging
import sys
import json
import random

from volttron.platform.vip.agent import Agent, Core, PubSub, compat, RPC
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from DCMGClasses.CIP import tagClient
from DCMGClasses.resources.misc import listparse
from DCMGClasses.resources.math import interpolation, combin
from DCMGClasses.resources import control, resource, customer, optimization
from DCMGClasses.resources.demand import appliances, human


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
        self.appliances = self.config["appliances"]
        self.demandCurve = self.config["demandCurve"]
        self.refload = float(self.config["refload"])
        self.perceivedInsol = 10
        #the following variables 
        self.FREGpart = bool(self.config["FREGpart"])
        self.DRpart = bool(self.config["DRpart"])
        
        self.Resources = []
        self.Appliances = []
        self.Devices = []
        
        
        loclist = self.location.split('.')
        if type(loclist) is list:
            if loclist[0] == "DC":
                self.grid, self.branch, self.bus, self.load = loclist
            elif loclist[0] == "AC":
                pass
            else:
                print("the first part of the location path should be AC or DC")
                
        self.branchNumber = self.branch[-1]
        self.busNumber = self.bus[-1]
        self.loadNumber = self.load[-1]
        
        self.relayTag = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_User".format(branch = self.branchNumber, bus = self.busNumber, load = self.loadNumber)
        self.currentTag = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_Current".format(branch = self.branchNumber, bus = self.busNumber, load = self.loadNumber)
        self.voltageTag = "BRANCH_{branch}_BUS_{bus}_Voltage".format(branch = self.branchNumber, bus = self.busNumber)
        
        
        #create resource objects for resources
        resource.makeResource(self.resources,self.Resources,True)
        for app in self.appliances:
            if app["type"] == "heater":
                newapp = appliances.HeatingElement(**app)
                newapp.associatedbehavior = human.EnergyBehavior("heater",newapp,human.QuadraticCostFn(.1,0,38))
                self.Appliances.append(newapp)
                print("ADDED A NEW APPLIANCE TO APPLIANCE LIST:")
                newapp.printInfo(1)
            else:
                pass
            
        #Both smart appliances and distributed resources are considered Devices
        #it is useful to consider the two of these together sometimes
        self.Devices.extend(self.Resources)
        self.Devices.extend(self.Appliances)
                    
        self.DR_participant = False
        self.FREG_participant = False
        self.gridConnected = False
        self.registered = False
        
        self.marginalutility = .2
        self.avgEnergyCost = 1
        self.outstandingSupplyBids = []
        self.outstandingDemandBids = []
        
        start = datetime.now()
        #this value doesn't matter
        end = start + timedelta(seconds = 30)
        
        self.PlanningWindow = control.Window(self.name,6,1,start,30)
        self.CurrentPeriod = control.Period(0,start,end)
        self.NextPeriod = self.PlanningWindow.periods[0]
        self.CurrentPeriod.nextperiod = self.NextPeriod
        
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
        
    def costFn(self,period,statecomps):
        #the costFn() method is implemented at the level of the User class
        #to allow the implementation of cost functions that are not independent
        #of other devices
        
        #for now, my cost functions are independent
        totalcost = 0
        for devkey in statecomps:
            #print(devkey)
            dev = listparse.lookUpByName(devkey, self.Devices)
            totalcost += dev.costFn(period,statecomps[devkey])
            
        return totalcost
    
    #update expectations regarding future prices
    def priceForecast(self):
        for period in self.PlanningWindow.periods:
            if self.currentSpot:
                period.expectedenergycost = self.currentSpot
            elif self.CurrentPeriod.plan.acceptedBids:
                period.expectedenergycost = self.CurrentPeriod.plan.acceptedBids[0].rate
            else:
                if settings.DEBUGGING_LEVEL >= 2:
                    print("HOMEOWNER {me} no official rate announced".format(me = self.name))
                period.expectedenergycost = settings.ASSUMED_RATE
        
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
        if newdemand == 0:
            self.disconnectLoad()
        else:
            if self.gridConnected:
                pass
            else:
                self.connectLoad()
        
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
                side = mesdict.get("side",None)
                period = mesdict.get("period",None)
                counterparty = messageSender
                if self.Resources:
                    biddict = {}
                    biddict["message_subject"] = "bid_response"
                    biddict["message_target"] = messageSender
                    biddict["message_sender"] = self.name
                    if side == "demand":
                        #determine amount and rate
                        bidcomponents = self.generateDemandBids()
                        
                        for bidcomp in bidcomponents:
                            amount = bidcomp.get("amount")
                            rate = bidcomp.get("rate")
                            biddict["amount"] = amount
                            biddict["rate"] = rate
                            biddict["side"] = side
                            biddict["counterparty"] = counterparty
                            biddict["duration"] = 1
                            biddict["period"] = period
                            #add to local list of outstanding bids
                            newBid = control.DemandBid(amount,rate,counterparty,period)
                            self.outstandingDemandBids.append(newBid)
                            biddict["uid"] = newBid.uid
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("\nHOME AGENT {me} ADDED AN OUTSTANDING DEMAND BID: {id}".format(me = self.name, id = newBid.uid))
                                print("HERE'S THE LIST OF OUTSTANDING DEMAND BIDS:")
                                for bid in self.outstandingDemandBids:
                                    bid.printInfo()
                                            
                            #and send to utility for consideration
                            mess = json.dumps(biddict)
                            self.vip.pubsub.publish(peer = "pubsub",topic = "energymarket",headers = {}, message = mess)
                            
                    elif side == "supply":
                        for res in self.Resources:
                            if type(res) is resource.SolarPanel:
                                amount = res.maxDischargePower*self.perceivedInsol/100
                                rate = control.ratecalc(res.capCost,.05,res.amortizationPeriod,.2)
                                biddict["amount"] = amount
                                biddict["service"] = service
                                biddict["side"] = side
                                biddict["rate"] = rate
                                biddict["counterparty"] = counterparty
                                biddict["duration"] = 1
                                biddict["period"] = period
                                biddict["resource"] = res.name
                                #add to local list of outstanding bids
                                newBid = control.SupplyBid(res.name,service,amount,rate,counterparty,period)
                                self.outstandingSupplyBids.append(newBid)
                                biddict["uid"] = newBid.uid
                                if settings.DEBUGGING_LEVEL >= 2:
                                    print("\nHOME AGENT {me} ADDED AN OUTSTANDING BID: {id}".format(me = self.name, id = newBid.uid))
                                    print("HERE'S THE LIST OF OUTSTANDING BIDS:")
                                    for bid in self.outstandingSupplyBids:
                                        bid.printInfo()
                                        
                                #and send to utility for consideration
                                mess = json.dumps(biddict)
                                self.vip.pubsub.publish(peer = "pubsub",topic = "energymarket",headers = {}, message = mess)
                                
                            elif type(res) is resource.LeadAcidBattery:
                                if res.SOC > .2:
                                    amount = 10
                                    rate = max(control.ratecalc(res.capCost,.05,res.amortizationPeriod,.05),self.capCost/self.cyclelife) + self.avgEnergyCost*amount
                                    bid["amount"] = amount
                                    bid["service"] = service
                                    biddict["side"] = side
                                    bid["rate"] = rate
                                    bid["counterparty"] = counterparty
                                    bid["duration"] = 1
                                    bid["period"] = period
                                    bid["resource"] = res.name
                                    
                                    newBid = control.Bid(res.name,service,amount,rate,counterparty,period)
                                    self.outstandingSupplyBids.append(newBid)
                                    
                                    if settings.DEBUGGING_LEVEL >= 2:
                                        print("\nHOME AGENT {me} ADDED AN OUTSTANDING BID: {id}".format(me = self.name, id = newBid.uid))
                                        print("HERE'S THE LIST OF OUTSTANDING BIDS:")
                                        for bid in self.outstandingSupplyBids:
                                            bid.printInfo()
                                        
                                    mess = json.dumps(bid)
                                    self.vip.pubsub.publish(peer = "pubsub",topic = "energymarket",headers = {}, message = mess)
                                
                            else:
                                print("A PROBLEM: {type} is not a recognized type".format(type = type(res)))
            #received when a homeowner's bid has been accepted    
            elif messageSubject == 'bid_acceptance':
                #if acceptable, update the plan
                side = mesdict.get("side",None)
                amount = mesdict.get("amount",None)
                rate = mesdict.get("rate",None)
                period = mesdict.get("period",None)
                uid = mesdict.get("uid",None)
                
                #amount or rate may have been changed
                #service also may have been changed from power to regulation
                if side == "supply":
                    service = mesdict.get("service",None)
                    for bid in self.outstandingSupplyBids:
                        print("HOME AGENT {me} COMPARING REC:{rec}|STORED:{sto}".format(me = self.name, rec = uid, sto = bid.uid))
                        if bid.uid == uid:
                            bid.service = service
                            bid.amount = amount
                            bid.rate = rate
                            bid.period = period
                            #if bid.period == self.NextPeriod.periodNumber:
                            #    self.NextPeriod.plan.addBid(bid)
                            
                            #look up object from period number and add bid
                            bidperiod = self.PlanningWindow.getPeriodByNumber(bid.period)
                            if bidperiod:
                                bidperiod.plan.addBid(bid)
                            else:
                                print("bid is not for a period in the planning window")
                                
                            self.outstandingSupplyBids.remove(bid)
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("\n-->HOMEOWNER {me} ACK SUPPLY BID ACCEPTANCE".format(me = self.name))
                                bid.printInfo()
                elif side == "demand":
                    for bid in self.outstandingDemandBids:
                        print("HOME AGENT {me} COMPARING REC:{rec}|STORED:{sto}".format(me = self.name, rec = uid, sto = bid.uid))
                        if bid.uid == uid:
                            bid.amount = amount
                            bid.rate = rate
                            bid.period = period
                            #if bid.period == self.NextPeriod.periodNumber:
                            #    self.NextPeriod.plan.addConsumption(bid)
                            bidperiod = self.PlanningWindow.getPeriodByNumber(bid.period)
                            if bidperiod:
                                bidperiod.plan.addConsumption(bid)
                            else:
                                print("bid is not for a period in the planning window")
                                
                            self.outstandingDemandBids.remove(bid)
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("\n-->HOMEOWNER {me} ACK DEMAND BID ACCEPTANCE".format(me = self.name))
                                bid.printInfo()
                
            elif messageSubject == "bid_rejection":
                #if the bid is not accepted, just remove the bid from the list of outstanding bids
                uid = mesdict.get("uid",None)
                side = mesdict.get("side",None)
                
                if side == "supply":
                    for bid in self.outstandingSupplyBids:
                        if bid.uid == uid:
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("\n-->HOMEOWNER {me} ACK BID REJECTION FOR {id}".format(me = self.name, id = bid.uid))
                                bid.printInfo()
                            self.outstandingSupplyBids.remove(bid)                    
                elif side == "demand":        
                    for bid in self.outstandingDemandBids:
                        if bid.uid == uid:
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("\n-->HOMEOWNER {me} ACK DEMAND BID REJECTION FOR {id}".format(me = self.name, id = bid.uid))
                                bid.printInfo()
                            self.outstandingDemandBids.remove(bid)
                        
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
                        self.NextPeriod = control.Period(period,startdtime,enddtime)
                        #schedule a callback to begin the new period
                        self.core.schedule(startdtime,self.advancePeriod)
            elif messageSubject == "rate_announcement":
                self.currentSpot = mesdict.get("rate")
                self.priceChange(self.currentSpot)
                
    
    def homefeed(self,peer,sender,bus,topic,headers,message):
        mesdict = json.loads(message)
        messageTarget = mesdict.get('message_target',None)
        if listparse.isRecipient(messageTarget,self.name):
            messageSubject = mesdict.get('message_subject',None)
            messageSender = mesdict.get('message_sender',None)
            
                
    def weatherfeed(self,peer,sender,bus,topic,headers,message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get('message_subject',None)
        messageTarget = mesdict.get('message_target',None)
        messageSender = mesdict.get('message_sender',None)
        messageTypes = mesdict.get("message_type",None)
        
        if listparse.isRecipient(messageTarget,self.name):    
            foredict = {}
            if messageSubject == "nowcast":
                for msg in messageTypes:
                    if msg[0] == "solar_irradiance":
                        foredict[msg[0]] = msg[1]
                    elif msg[0] == "wind_speed":
                        foredict[msg[0]] = msg[1]
                    elif msg[0] == "temperature":
                        foredict[msg[0]] = msg[1]
                self.CurrentPeriod.add(Forecast(foredict,self.CurrentPeriod))
            elif messageSubject == "forecast":
                periodnumber = mesdict.get("forecast_period")
                for msg in messageTypes:
                    if msg[0] == "solar_irradiance":
                        foredict[msg[0]] = msg[1]
                    elif msg[0] == "wind_speed":
                        foredict[msg[0]] = msg[1]
                    elif msg[0] == "temperature":
                        foredict[msg[0]] = msg[1]
                period = self.PlanningWindow.getPeriodByNumber(periodnumber)
                period.addForecast(Forecast(foredict,period))
                
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
                            print("\nHOME {me} opted in to DR program".format(me = self.name) )
                    
                elif type == "enrollment_confirm":
                    self.DR_participant = True    
                    
        
    def planningRemakeWindow(self,debug = False):
        if debug:
            print("HOMEOWNER {me} coming up with new plan".format(me = self.name))
        
        #remake plans from end of window forward
        selperiod = self.PlanningWindow.periods[-1]
        while selperiod:
            self.planningRemakePeriod(selperiod,True)
            selperiod = selperiod.previousperiod
    
    def planningRemakePeriod(self,period,debug = False):
        if debug:
            print(">HOMEOWNER {me} now working on period {per}".format(me = self.name, per = period.periodNumber))
            
        #remake grid points
        self.makeDPGrid(period,True)
        #remake new inputs
        if not period.plan.stategrid.grid:
            print("Homeowner {me} encountered a missing state grid for period {per}".format(me = self.name, per = period.periodNumber))
            return
        for state in period.plan.stategrid.grid:
            #if this is not the last period
            if period.nextperiod:
                if debug:
                    print(">WORKING ON A NEW STATE: {sta}".format(sta = state.components))
                #make inputs for the state currently being examined
                self.makeInputs(state,period)
                if debug:
                    print(">EVALUATING {n} ACTIONS".format(n = len(period.plan.admissiblecontrols)))
                
                #find the best input for this state
                currentbest = float('inf')
                for input in period.plan.admissiblecontrols:
                    self.findInputCost(state,input,period,settings.ST_PLAN_INTERVAL,True)
                    if input.pathcost < currentbest:
                        if debug:
                            print(">NEW BEST OPTION! {newcost} < {oldcost}".format(newcost = input.pathcost, oldcost = currentbest))
                        currentbest = input.pathcost
                        #associate state with optimal input
                        state.setoptimalinput(input)
                    else:
                        if debug:
                            print(">NOT AS GOOD {newcost} >= {oldcost}".format(newcost = input.pathcost, oldcost = currentbest))
                
                
                if debug:
                    print(">HOMEOWNER {me}: optimal input for state {sta} is {inp}".format(me = self.name, sta = state.components, inp = state.optimalinput.components))
            else:
                if debug:
                    print(">HOMEOWNER {me}: this is the final period in the window".format(me = self.name))
                    state.printInfo()
                
    def findInputCost(self,state,input,period,duration,debug = False):
        if debug:
            print(">>HOMEOWNER {me}: finding cost for input {inp}".format(me = self.name, inp = input.components))
        #find next state if this input is applied
        comps = self.applySimulatedInput(state,input,duration,True)
        
        #if the next period is not the last, consider the path cost
        if period.nextperiod.nextperiod:
            #cost of optimal path from next state forward
            pathcost = period.nextperiod.plan.stategrid.interpolatepath(comps,True)
        else:
            #otherwise, only consider the statecost 
            pathcost = 0
        #add cost of being in next state for next period
        pathcost += period.nextperiod.plan.stategrid.interpolatestate(comps,True)
        
        #cost of getting to next state with t
        totaltrans = 0
        for key in input.components:
            dev = listparse.lookUpByName(key, self.Devices)
            totaltrans += dev.inputCostFn(input.components[key],period.nextperiod,state,duration)
        input.pathcost = pathcost + totaltrans
        
        if debug:
            print(">>HOMEOWNER {me}: transition cost is {trans}, total path cost is {path}".format(me = self.name, trans = totaltrans, path = input.pathcost))
        
        return input.pathcost
    
            
    def applySimulatedInput(self,state,input,duration,debug = False):
        total = 0
        newstatecomps = {}
        
        for devname in state.components:
            devstate = state.components[devname]
            devinput = input.components[devname]
            newstate = listparse.lookUpByName(devname,self.Devices).applySimulatedInput(devstate,devinput,duration)
            newstatecomps[devname] = newstate
        
        if debug:
            print(">>>HOMEOWNER {me}: starting state is {start}, ending state is {end}".format(me = self.name, start = state.components, end = newstatecomps))
        
        return newstatecomps
        
    def makeDPGrid(self,period,debug = False):
        inputdict = {}
        
        for dev in self.Devices:
            if dev.gridpoints:
                inputdict[dev.name] = dev.gridpoints
            
        devstates = combin.makeopdict(inputdict)
        
        period.plan.makeGrid(period,devstates,self.costFn)
        
        if debug:
            print("HOMEOWNER {me} made state grid for period {per} with {num} points".format(me = self.name, per = period.periodNumber, num = len(period.plan.stategrid.grid)))
        
        
    def makeInputs(self,state,period,debug = False):
        inputdict = {}
        inputs = []
        
        for dev in self.Devices:
            if dev.actionpoints:
                inputdict[dev.name] = dev.actionpoints
            
        devactions = combin.makeopdict(inputdict)
        
        #generate input components
        #grid connected inputs
        if period.pendingdrevents:
            for devact in devactions:
                inputs.append(optimization.InputSignal(devact,True,period.pendingdrevents[0]))
        
        #no DR participation
        for devact in devactions:
            inputs.append(optimization.InputSignal(devact,True,None))
            
        #non grid connected inputs
        #do this later... needs special consideration
        
        if debug:
            print("HOMEOWNER {me} made input list for period {per} with {num} points".format(me = self.name, per = period.periodNumber, num = len(inputs)))
        
        
        for input in inputs:
            #weed out inadmissible inputs
            if not self.admissibleInput(input,state,period,True): 
                inputs.remove(input)
            else:
                #input is admissible keep going
                #sum cost of all actions
                total = 0
                for devkey in input.components:
                    device = listparse.lookUpByName(devkey,self.Devices)
                    total += device.inputCostFn(input.components[devkey],period,state,settings.ST_PLAN_INTERVAL) 
                
                input.setcost(total)
                
        #having generated the list of admissible inputs and computed their costs
        #we replace any previously existing list of admissible controls for the
        #period's plan with this one
        
        period.plan.setAdmissibleInputs(inputs)
        
        
    def admissibleInput(self,input,state,period,debug = False):
        #sum power from all components
        totalsource = 0
        totalsink = 0
        maxavail = 0
        
        for compkey in input.components:
            device = listparse.lookUpByName(compkey,self.Devices)
            if device.issource:
                #we may be dealing with a source or storage element
                #the sign of the setpoint must indicate whether it is acting as a source or sink
                
                #is the disposition of the device consistent with its state?
                if device.statebehaviorcheck(state,input):
                    pass
                else:
                    #input not consistent with state
                    if debug:
                        print("inadmissible input: input doesn't make sense for this state")
                    return False
                #keep track of contribution from source
                totalsource += device.getPowerFromPU(input.components[compkey])
            else:
                if device.issink:
                    #we're dealing with a device that is only a sink
                    #whatever the sign of its setpoint, it is consuming power
                    totalsink += device.getPowerFromPU(input.components[compkey])
            
            if device.issource:
                if device.isintermittent:
                    #get maximum available power for intermittent sources
                    maxavail += self.checkForecastAvailablePower(device,period)
                    if input.components[compkey] > maxavail:
                        #power contribution exceeds expected capability
                        if debug:
                            print("inadmissible input: {name} device contribution exceeds expected capability")
                        return False
                else:
                    maxavail += device.maxDischargePower
            
                
        totalnet = totalsource - totalsink
        
        minpower = 0
        maxpower = 0
        
        if not input.gridconnected:
            if totalnet != 0:
                #not connected to grid, all load must be locally served
                if debug:
                    print("Inadmissible input: source and load must balance when not grid connected")
                
        if input.drevent:
            dr = input.drevent
            if isinstance(dr,CurtailmentEvent):
                if input.gridconnected:
                    minpower = 0
                    maxpower = self.getDRPower(dr)
                else:
                    minpower = 0
                    maxpower = self.getLocallyAvailablePower()
            elif isinstance(dr,LoadUpEvent):
                if input.gridconnected:
                    minpower = self.getDRPower(dr)
                    maxpower = 999
                else:
                    #can't load up if we aren't loading at all
                    if debug:
                        print("inadmissible input: load up and disconnect")  # just for debugging
                    return False
            else:
                #if not participating in a DR event
                if input.gridconnected:
                    minpower = -999
                    maxpower = 999
                else:
                    minpower = 0
                    
        
        return True
    
    def checkForecastAvailablePower(self,device,period):
        irradiance = self.checkForecast(device,period)
        power = device.powerAvailable(irradiance)
        return power
    
    def checkForecast(self,device,period):
        if period.forecast:
            if device.environmentalVariable in period.forecast.data:
                return period.forecast.data[device.environmentalVariable]
            else:
                print("Agent {me}'s forecast for period {per} doesn't include data for {dat}".format(me = self.name, per = period.periodNumber,dat = device.environmentalVariable))
                
        else:
            print("Agent {me} doesn't have a forecast for period {per} yet".format(me = self.name, per = period.periodNumber))
            self.requestForecast(period)
    
    def getDRpower(self,event):
        if event.spec == "reducebypercent":
            pass
        
    def getLocallyAvailablePower(self,period):
        total = 0
        for res in self.Resources:
            total += self.forecastAvailPower(period,res)
            
        return total
    
    def requestForecast(self,period):
        mesdict = {}
        mesdict["message_sender"] = self.name
        mesdict["message_target"] = "Goddard"
        mesdict["message_subject"] = "forecast"
        mesdict["message_type"] = ["solar_irradiance", "wind_speed", "temperature"]
        mesdict["forecast_time"] = period.startTime.strptime(startTime,"%Y-%m-%dT%H:%M:%S.%f")
        mesdict["forecast_period"] = period.periodNumber
        
        mes = json.dumps(mesdict)
        self.vip.pubsub.publish("pubsub","weatherservice",{},mes)

        
        
    def simStep(self,state,input,tstep):
        for app in self.Appliances:
            app.simulationStep(state,input,tstep)
        
    def generateDemandBids(self):
        ''''a load agent that can vary its consumption might want to split up its
        total consumption into components at different rates'''
        
        bidcomponents = []
        
        #maybe later this will be a loop for generating multiple bids from demand curve
        bid ={"amount":  self.refload, "rate": self.marginalutility }        
        bidcomponents.append(bid)
        return bidcomponents

    def changeConsumption(self, level):
        if level == 0:
            self.disconnectLoad()
        elif level == 1:
            self.connectLoad()
        else:
            pass
        
    def advancePeriod(self):
        self.CurrentPeriod = self.PlanningWindow.periods[0]
        self.PlanningWindow.shiftWindow()
        self.NextPeriod = self.PlanningWindow.periods[0]
        
        #run new price forecast
        self.priceForecast()
        
        #make a new plan over entire window
        if settings.DEBUGGING_LEVEL >= 1:
            print("HOMEOWNER {me} remaking planning window".format(me = self.name))
        self.planningRemakeWindow(True)
        
        #contra the utility version of this fn, don't create the next period
        
        if settings.DEBUGGING_LEVEL >= 1:
            print("\nHOMEOWNER AGENT {me} moving into new period:".format(me = self.name))
            self.CurrentPeriod.printInfo()
        
        #call enact plan
        self.enactPlan()
        
        #also don't schedule next call, wait for announcement from utility
    
    '''responsible for enacting the plan which has been defined for a planning period'''
    def enactPlan(self):
        #involvedResources will help figure out which resources must be disconnected
        involvedResources = []
        #change setpoints
        if self.CurrentPeriod.plan:
            if settings.DEBUGGING_LEVEL >= 2:
                print("RESIDENCE {me} IS ENACTING ITS PLAN FOR PERIOD {per}".format(me = self.name, per = self.CurrentPeriod.periodNumber))
                
            for bid in self.CurrentPeriod.plan.ownBids:
                res = listparse.lookUpByName(bid.resourceName,self.Resources)
                involvedResources.append(res)
                #if the resource is already connected, change the setpoint
                if res.connected == True:
                    if settings.DEBUGGING_LEVEL >= 2:
                        print(" Resource {rname} is already connected".format(rname = res.name))
                    if bid.service == "power":
                        #res.DischargeChannel.ramp(bid.amount)
                        res.DischargeChannel.changeSetpoint(bid.amount)
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("Power resource {rname} setpoint to {amt}".format(rname = res.name, amt = bid.amount))
                    elif bid.service == "reserve":
                        #res.DischargeChannel.ramp(.1)
                        res.DischargeChannel.changeReserve(bid.amount,-.2)
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("Reserve resource {rname} setpoint to {amt}".format(rname = res.name, amt = bid.amount))
                #if the resource isn't connected, connect it and ramp up power
                else:
                    if bid.service == "power":
                        #res.connectSourceSoft("Preg",bid.amount)
                        res.DischargeChannel.connectWithSet(bid.amount,0 )
                        if settings.DEBUGGING_LEVEL >= 2:
                                print("Connecting resource {rname} with setpoint: {amt}".format(rname = res.name, amt = bid.amount))
                    elif bid.service == "reserve":
                        #res.connectSourceSoft("Preg",.1)
                        res.DischargeChannel.connectWithSet(bid.amount, -.2)
                        if settings.DEBUGGING_LEVEL >= 2:
                                print("Committed resource {rname} as a reserve with setpoint: {amt}".format(rname = res.name, amt = bid.amount))
            #ramp down and disconnect resources that aren't being used anymore
            for res in self.Resources:
                if res not in involvedResources:
                    if res.connected == True:
                        #res.disconnectSourceSoft()
                        res.DischargeChannel.disconnect()
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("Resource {rname} no longer required and is being disconnected".format(rname = res.name))
                            
            if self.CurrentPeriod.plan.plannedConsumption:
                self.changeConsumption(1)
            else:
                self.changeConsumption(0)
    
    def disconnectLoad(self):
        #we can disconnect load at will
        tagClient.writeTags([self.relayTag],[False])
        
    
    def connectLoad(self):
        #if we are not already connected, we need permission from the utility
        mesdict = {"message_subject" : "request_connection",
                   "message_sender" : self.name,
                   "message_target" : "ENERCON"
                   }
        if settings.DEBUGGING_LEVEL >= 2:
            print("Homeowner {me} asking utility {them} for connection".format(me = self.name, them = mesdict["message_target"]))
        
        mess = json.dumps(mesdict)
        self.vip.pubsub.publish(peer = "pubsub",topic = "customerservice",headers = {}, message = mess)
        
        #tagName = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_User".format(branch = self.branch, bus = self.bus, load = self.load)
        #setTagValue(tagName,True)
        #tagClient.writeTags([tagName],[True])
        
    def measureVoltage(self):
        tag = "BRANCH{branch}_BUS{bus}_LOAD{load}_Current".format(branch = self.branch, bus = self.bus, load = self.load)
        return tagClient.readTags([tag])
    
    def measureCurrent(self):
        tag = "BRANCH{branch}_BUS{bus}_LOAD{load}_Current".format(branch = self.branch, bus = self.bus, load = self.load)
        return tagClient.readTags([tag])
    
    def measurePower(self):
        return self.measureVoltage()*self.measureCurrent()
        
    def printInfo(self,depth):
        print("\n________________________________________________________________")
        print("~~SUMMARY OF HOME STATE~~")
        print("HOME NAME: {name}".format(name = self.name))
        if 'self.CurrentPeriod' in globals():
            print("PERIOD: {per}".format(per = self.CurrentPeriod.periodNumber))
            print(">>>START: {start}  STOP: {end}".format(start = self.CurrentPeriod.startTime, end =  self.CurrentPeriod.endTime))
        print("HERE IS MY CURRENT PLAN:")
        self.CurrentPeriod.plan.printInfo(1)
        
        print("SMART APPLIANCES:")
        for app in self.Appliances:
            app.printInfo(1)
        print("LIST ALL OWNED RESOURCES ({n})".format(n = len(self.Resources)))
        for res in self.Resources:
            res.printInfo(1)
        
        print("__________________________________________________________________")
        
    
def main(argv = sys.argv):
    '''Main method called by the eggsecutable'''
    try:
        utils.vip_main(HomeAgent)
    except Exception as e:
        _log.exception('unhandled exception')
        
if __name__ == '__main__':
    sys.exit(main())