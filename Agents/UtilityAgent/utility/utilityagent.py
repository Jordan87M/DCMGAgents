from __future__ import absolute_import
from datetime import datetime, timedelta
import logging
import sys
import json
import operator
import random

from volttron.platform.vip.agent import Agent, BasicCore, core, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

#from DCMGClasses.CIP import wrapper
from DCMGClasses.CIP import tagClient
from DCMGClasses.resources.misc import listparse
from DCMGClasses.resources.math import interpolation, graph
from DCMGClasses.resources import resource, groups, financial, control, customer


from . import settings
from zmq.backend.cython.constants import RATE
from __builtin__ import True
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
    
       

    uid = 0
    
    infrastructureTags = ["BRANCH_1_BUS_1_PROXIMAL_User",
                          "BRANCH_1_BUS_2_PROXIMAL_User",
                          "BRANCH_2_BUS_1_PROXIMAL_User",
                          "BRANCH_2_BUS_2_PROXIMAL_User",
                          "BRANCH_1_BUS_1_DISTAL_User",
                          "BRANCH_1_BUS_2_DISTAL_User",
                          "BRANCH_2_BUS_1_DISTAL_User",
                          "BRANCH_2_BUS_2_DISTAL_User",
                          "INTERCONNECT_1_User",
                          "INTERCONNECT_2_User"]
    
    
    def __init__(self,config_path,**kwargs):
        super(UtilityAgent,self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config['agentid']
        self.state = "init"
        
        self.name = self.config["name"]
        self.resources = self.config["resources"]
        self.Resources = []
        self.groupList = []
        self.supplyBidList = []
        self.demandBidList = []
        self.reserveBidList = []
        
        self.nodes = [groups.Node("DC.MAIN.MAIN",[],None,[]),
                        groups.Node("DC.BRANCH1.BUS1",[],None,[]),
                        groups.Node("DC.BRANCH1.BUS2",[],None,[]),
                        groups.Node("DC.BRANCH2.BUS1",[],None,[]),
                        groups.Node("DC.BRANCH2.BUS2",[],None,[])]
        self.nodes[0].addEdge(self.nodes[1], "to", "BRANCH_1_BUS_1_Current")
        self.nodes[0].addEdge(self.nodes[3], "to", "BRANCH_2_BUS_1_Current")
        
        self.nodes[1].addEdge(self.nodes[0], "from", "BRANCH_1_BUS_1_Current")
        self.nodes[1].addEdge(self.nodes[2], "to", "BRANCH_1_BUS_2_Current")
        self.nodes[1].addEdge(self.nodes[3], "to", "INTERCONNECT_1_Current")
        
        self.nodes[2].addEdge(self.nodes[1], "from", "BRANCH_1_BUS_2_Current" )
        self.nodes[2].addEdge(self.nodes[4], "to", "INTERCONNECT_2_Current" )
        
        self.nodes[3].addEdge(self.nodes[0], "from", "BRANCH_2_BUS_1_Current")
        self.nodes[3].addEdge(self.nodes[1], "from", "INTERCONNECT_1_Current")
        self.nodes[3].addEdge(self.nodes[4], "to", "BRANCH_2_BUS_2_Current")
        
        self.nodes[4].addEdge(self.nodes[2], "from", "INTERCONNECT_2_Current")
        self.nodes[4].addEdge(self.nodes[3], "from", "BRANCH_2_BUS_2_Current")
        
        #import list of utility resources and make into object
        resource.addResource(self.resources,self.Resources,False)
        #add resources to node objects based on location
        for res in self.Resources:
            for node in self.nodes:
                if res.location.split(".")[0:3] == node.name.split("."):
                    node.resources.append(res)
            
        
        self.perceivedInsol = 75 #as a percentage of nominal
        self.customers = []
        self.DRparticipants = []
        
        #local storage to ease load on tag server
        self.tagCache = {}
        
        now = datetime.now()
        end = datetime.now() + timedelta(seconds = settings.ST_PLAN_INTERVAL)
        self.CurrentPeriod = control.Period(0,now,end,self.name)
        
        self.NextPeriod = control.Period(1,end,end + timedelta(seconds = settings.ST_PLAN_INTERVAL),self.name)
        
        self.bidstate = BidState()
        
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
        
        
        #schedule planning period advancement
        self.core.schedule(self.NextPeriod.startTime,self.advancePeriod)
    
    '''callback for weatherfeed topic'''
    def weatherfeed(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get('message_subject',None)
        messageTarget = mesdict.get('message_target',None)
        messageSender = mesdict.get('message_sender',None)
        messageType = mesdict.get("message_type",None)
        #if we are the intended recipient
        if listparse.isRecipient(messageTarget,self.name):    
            if messageSubject == "nowcast":
                if messageType == "solar_irradiance":
                    #update local solar irradiance estimate
                    self.perceivedInsol = mesdict.get("info",None)
    
    '''callback for customer service topic. This topic is used to enroll customers
    and manage customer accounts.'''    
    def customerfeed(self, peer, sender, bus, topic, headers, message):
        #load json message
        try:
            mesdict = json.loads(message)
        except Exception as e:
            print("customerfeed message to {me} was not formatted properly".format(me = self))
        #determine intended recipient, ignore if not us    
        messageTarget = mesdict.get("message_target",None)
        if listparse.isRecipient(messageTarget,self.name):
            
            if settings.DEBUGGING_LEVEL >= 3:
                print(message)
            
            messageSubject = mesdict.get("message_subject",None)
            messageType = mesdict.get("message_type",None)
            if messageSubject == "customer_enrollment":
                #if the message is a response to new customer solicitation
                if messageType == "new_customer_response":
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("UTILITY {me} RECEIVED A RESPONSE TO CUSTOMER ENROLLMENT SOLICITATION".format(me = self.name))
                    try:
                        name, location, resources, customerType = mesdict.get("info")                        
                    except Exception as e:
                        print("customer information improperly formatted :(")
                    #create a new object to represent customer in our database    
                    if customerType == "residential":
                        cust = customer.ResidentialCustomerProfile(name,location,resources)
                        self.customers.append(cust)
                    elif customerType == "commercial":
                        cust = customer.CommercialCustomerProfile(name,location,resources)
                        self.customers.append(cust)
                    else:                        
                        pass
                    
                    #add customer to Node object
                    for node in self.nodes:
                        if cust.location.split(".")[0:3] == node.name.split("."):
                            node.customers.append(cust)
                    
                    #add resources to resource pool if present
                    if resources:
                        for resource in resources:
                            addOneToPool(self.resourcePool,resource)
                            #print(self.resourcePool)
                            for node in self.nodes:
                                if node.name.split(".") == resource["location"].split(".")[0:3]:
                                    resType = res.get("type",None)
                                    if resType == "solar":
                                        newres = customer.SolarProfile(**res)
                                    elif resType == "lead_acid_battery":
                                        newres = customer.LeadAcidBatteryProfile(**res)
                                    else:
                                        print("unsupported resource type")
                                    node.addResource(newres)
                                    cust.Resources.append(newres)
                                    
                                                     
                        
                    if settings.DEBUGGING_LEVEL >= 1:
                        print("\nNEW CUSTOMER ENROLLMENT ##############################")
                        print("UTILITY {me} enrolled customer {them}".format(me = self.name, them = name))
                        cust.printInfo(0)
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("...and here's how they did it:\n {mes}".format(mes = message))
                        print("#### END ENROLLMENT NOTIFICATION #######################")
                    
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
    
    ''' the accountUpdate() function polls customer power consumption/production
    and updates account balances according to their rate '''
    @Core.periodic(settings.ACCOUNTING_INTERVAL)
    def accountUpdate(self):
        for group in self.groupList:
            for cust in group.customers:
                power = cust.measurePower()
                energy = power*settings.ACCOUNTING_INTERVAL
                #credit transfer for period     
                balanceAdjustment = energy*group.rate*cust.rateAdjustment
                
               
                cust.customerAccount.adjustBalance(balanceAdjustment)
    
    @Core.periodic(settings.LT_PLAN_INTERVAL)
    def planLongTerm(self):
        pass
    
    @Core.periodic(settings.ANNOUNCE_PERIOD_INTERVAL)
    def announcePeriod(self):    
        mesdict = {"message_sender" : self.name,
                   "message_target" : "broadcast",
                   "message_subject" : "announcement",
                   "message_type" : "next_period_time",
                   "period_number" : self.NextPeriod.periodNumber,
                   "start_time" : self.NextPeriod.startTime.isoformat(),
                   "end_time" : self.NextPeriod.endTime.isoformat()
                   }
        
        if settings.DEBUGGING_LEVEL >= 2:
            print("\nUTILITY {me} ANNOUNCING period {pn} starting at {t}".format(me = self.name, pn = mesdict["period_number"], t = mesdict["start_time"]))
        message = json.dumps(mesdict)
        self.vip.pubsub.publish("pubsub","energymarket",{},message)
        
    def announceRate(self, recipient, rate, start):
        mesdict = {"message_sender" : self.name,
                   "message_subject" : "rate_announcement",
                   "message_target" : recipient.name,
                   "start_time" : start.isoformat(),
                   "rate" : rate
                   }
        message = json.dumps(mesdict)
        self.vip.pubsub.publish("pubsub","energymarket",{},message)
    
    @Core.periodic(settings.ST_PLAN_INTERVAL)
    def solicitBids(self):
        if settings.DEBUGGING_LEVEL >=2 :
            print("\nUTILITY {me} IS ASKING FOR BIDS FOR SHORT TERM PLANNING INTERVAL {int}".format(me = self.name, int = self.NextPeriod.periodNumber))
        subs = self.getTopology()
        self.printInfo(0)
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY {me} THINKS THE TOPOLOGY IS {top}".format(me = self.name, top = subs))
        
        '''first we have to find out how much it will cost to get power
        from various sources, both those owned by the utility and by 
        customers'''
        #clear the bid list in preparation for receiving new bids
        self.supplyBidList = []
        self.reserveBidList = []
        self.demandBidList = []
        #send bid solicitations to all customers who are known to have behind the meter resources
        self.bidstate.acceptall()
        for group in self.groupList:
            for cust in group.customers:
                # ask about consumption
                mesdict = {}
                mesdict["message_sender"] = self.name
                mesdict["message_subject"] = "bid_solicitation"
                mesdict["side"] = "demand"
                mesdict["message_target"] = cust.name
                mesdict["period"] = self.NextPeriod.periodNumber
                mesdict["solicitation_id"] = self.uid
                self.uid += 1
                
                mess = json.dumps(mesdict)
                self.vip.pubsub.publish(peer = "pubsub", topic = "energymarket", headers = {}, message = mess)
                    
                if settings.DEBUGGING_LEVEL >= 2:
                    print("UTILITY {me} SOLICITING CONSUMPTION BIDS: {mes}".format(me = self.name, mes = mess))
                    
                
                if cust.resources:
                    #ask about bulk power
                    mesdict = {}
                    mesdict["message_sender"] = self.name
                    mesdict["message_subject"] = "bid_solicitation"
                    mesdict["side"] = "supply"
                    mesdict["service"] = "power"
                    mesdict["message_target"] = cust.name
                    mesdict["period"] = self.NextPeriod.periodNumber
                    mesdict["solicitation_id"] = self.uid
                    self.uid += 1
                    
                    mess = json.dumps(mesdict)
                    self.vip.pubsub.publish(peer = "pubsub", topic = "energymarket", headers = {}, message = mess)
                    
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("UTILITY {me} SOLICITING BULK POWER BID: {mes}".format(me = self.name, mes = mess))
                    
                    #ask about reserves                    
                    mesdict["solicitation_id"] = self.uid
                    mesdict["service"] = "reserve"
                    self.uid += 1
                    
                    mess = json.dumps(mesdict)
                    self.vip.pubsub.publish(peer = "pubsub", topic = "energymarket", headers = {}, message = mess)
                    
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("UTILITY {me} SOLICITING RESERVE POWER BID: {mes}".format(me = self.name, mes = mess))
        sched = datetime.now() + timedelta(seconds = 10)            
        delaycall = self.core.schedule(sched,self.planShortTerm)
        
    def planShortTerm(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("\nUTILITY {me} IS FORMING A NEW SHORT TERM PLAN".format(me = self.name))
        
        #tender bids for the utility's own resources
        for res in self.Resources:
            if type(res) is resource.SolarPanel:
                amount = res.maxDischargePower*self.perceivedInsol/100
                rate = financial.ratecalc(res.capCost,.05,res.amortizationPeriod,.2)
                self.supplyBidList.append(financial.SupplyBid(res.name,"power",amount, rate, self.name, self.NextPeriod.periodNumber))
            elif type(res) is resource.LeadAcidBattery:
                amount = 10
                rate = max(financial.ratecalc(res.capCost,.05,res.amortizationPeriod,.05),self.capCost/self.cyclelife) + self.avgEnergyCost*amount
                self.supplyBidList.append(financial.SupplyBid(res.name,"power",amount, rate, self.name, self.NextPeriod.periodNumber))
            else:
                print("trying to plan for unknown resource type")
        
        for group in self.groupList:
            maxLoad = self.getMaxGroupLoad(group)
            if settings.DEBUGGING_LEVEL >= 2:
                print("\n\nPLANNING for GROUP {group}: worst case load is {max}".format(group = group.name, max = maxLoad))
                print(">>here are the supply bids:")
                for bid in self.supplyBidList:                    
                    bid.printInfo(0)
                print(">>here are the reserve bids:")
                for bid in self.reserveBidList:                    
                    bid.printInfo(0)          
                print(">>here are the demand bids:")          
                for bid in self.demandBidList:                    
                    bid.printInfo(0)
                
            
                    
            #sort array of supplier bids by rate from low to high
            self.supplyBidList.sort(key = operator.attrgetter("rate"))
            self.reserveBidList.sort(key = operator.attrgetter("rate"))
            #sort array of consumer bids by rate from high to low
            self.demandBidList.sort(key = operator.attrgetter("rate"),reverse = True)
            
            qrem = 0                #leftover part of bid
            supplyindex = 0
            demandindex = 0
            partialsupply = False
            partialdemand = False
            sblen = len(self.supplyBidList)
            rblen = len(self.reserveBidList)
            dblen = len(self.demandBidList)
            
            while supplyindex < sblen and demandindex < dblen:
                if settings.DEBUGGING_LEVEL >= 2:
                    print("\ndemand index: {di}".format(di = demandindex))
                    print("supply index: {si}".format(si = supplyindex))
                    
                if self.demandBidList[demandindex].rate > self.supplyBidList[supplyindex].rate:
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("demand rate {dr} > supply rate {sr}".format(dr = self.demandBidList[demandindex].rate, sr = self.supplyBidList[supplyindex].rate))
                        
                    group.rate = self.demandBidList[demandindex].rate
                    if partialsupply:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("partial supply bid: {qr} remaining".format(qr = qrem))
                        
                        if qrem > self.demandBidList[demandindex].amount:                            
                            qrem -= self.demandBidList[demandindex].amount
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("still {qr} remaining in supply bid".format(qr = qrem))
                            partialsupply = True
                            partialdemand = False
                            self.demandBidList[demandindex].accepted = True
                            demandindex += 1
                        elif qrem < self.demandBidList[demandindex].amount:        
                            qrem = self.demandBidList[demandindex].amount - qrem
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("exhausted supply bid, now {qr} left in demand bid".format(qr = qrem))
                            partialsupply = False
                            partialdemand = True
                            self.supplyBidList[supplyindex].accepted = True
                            supplyindex += 1                            
                        else:
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("exact match in bids")
                            qrem = 0
                            partialsupply = False
                            partialdemand = False     
                            self.supplyBidList[supplyindex].accepted = True   
                            self.demandBidList[demandindex].accepted = True 
                            supplyindex += 1
                            demandindex += 1       
                    elif partialdemand:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("partial demand bid: {qr} remaining".format(qr = qrem))
                            
                        if qrem > self.supplyBidList[supplyindex].amount:
                            qrem -= self.supplyBidList[supplyindex].amount
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("still {qr} remaining in supply bid".format(qr = qrem))
                            partialsupply = False
                            partialdemand = True
                            self.supplyBidList[supplyindex].accepted = True
                            supplyindex += 1
                        elif qrem < self.supplyBidList[supplyindex].amount:
                            qrem = self.supplyBidList[supplyindex].amount - qrem
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("exhausted demand bid, now {qr} left in supply bid".format(qr = qrem))
                            partialsupply = True
                            partialdemand = False
                            self.demandBidList[demandindex].accepted = True
                            demandindex += 1
                        else:
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("exact match in bids")
                            qrem = 0
                            partialsupply = False
                            partialdemand = False
                            self.supplyBidList[supplyindex].accepted = True   
                            self.demandBidList[demandindex].accepted = True 
                            supplyindex += 1
                            demandindex += 1
                    else:
                        if settings.DEBUGGING_LEVEL >= 2:
                                print("no partial bids")
                                
                        if self.demandBidList[demandindex].amount > self.supplyBidList[supplyindex].amount:
                            qrem = self.demandBidList[demandindex].amount - self.supplyBidList[supplyindex].amount
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("{qr} remaining in demand bid".format(qr = qrem))
                            partialdemand = True
                            partialsupply = False
                            supplyindex += 1
                        elif self.demandBidList[demandindex].amount < self.supplyBidList[supplyindex].amount:
                            qrem = self.supplyBidList[supplyindex].amount - self.demandBidList[demandindex].amount
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("{qr} remaining in supply bid".format(qr = qrem))
                            partialdemand = False
                            partialsupply = True
                            demandindex += 1
                        else:
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("bids match exactly")
                            qrem = 0
                            partialsupply = False
                            partialdeand = False
                            supplyindex += 1
                            demandindex += 1
                        self.supplyBidList[supplyindex].accepted = True
                        self.demandBidList[supplyindex].accepted = True
                else:
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("PAST EQ PRICE! demand rate {dr} < supply rate {sr}".format(dr = self.demandBidList[demandindex].rate, sr = self.supplyBidList[supplyindex].rate))
                    if partialsupply:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("still partial supply bid to take care of")
                        self.supplyBidList[supplyindex].accepted = True
                        self.supplyBidList[supplyindex].modified = True
                        self.supplyBidList[supplyindex].amount -= qrem
                        self.demandBidList[demandindex].accepted = False
                        partialsupply = False
                        partialdemand = False
                    elif partialdemand:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("still partial demand bid to take care of")
                        self.demandBidList[demandindex].accepted = True
                        self.demandBidList[demandindex].modified = True
                        self.demandBidList[demandindex].amount -= qrem
                        self.supplyBidList[supplyindex].accepted = False
                        partialsupply = False
                        partialdemand = False
                    else:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("reject and skip...")
                        self.supplyBidList[supplyindex].accepted = False
                        self.demandBidList[demandindex].accepted = False
                    supplyindex += 1
                    demandindex += 1
            
            while supplyindex < sblen:
                if settings.DEBUGGING_LEVEL >= 2:
                    print(" out of loop, still cleaning up supply bids {si}".format(si = supplyindex))
                if partialsupply:
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("partial supply bid to finish up")
                    self.supplyBidList[supplyindex].accepted = True
                    self.supplyBidList[supplyindex].modified = True
                    self.supplyBidList[supplyindex].amount -= qrem
                    partialsupply = False
                    partialdemand = False
                else:
                    self.supplyBidList[supplyindex].accepted = False
                supplyindex += 1
                
            while demandindex < dblen:
                if settings.DEBUGGING_LEVEL >= 2:
                    print(" out of loop, still cleaning up demand bids {di}".format(di = demandindex))
                if partialdemand:
                    if settings.DEBUGGING_LEVEL >= 2:
                        print("partial demand bid to finish up")
                    self.demandBidList[demandindex].accepted = True
                    self.demandBidList[demandindex].modified = True
                    self.demandBidList[demandindex].amount -= qrem
                    partialsupply = False
                    partialdemand = False
                else:
                    self.demandBidList[demandindex].accepted = False
                demandindex += 1
                    
            
            totalsupply = 0    
            #notify the counterparties of the terms on which they will supply power
            for bid in self.supplyBidList:
                if bid.accepted:
                    totalsupply += bid.amount
                    self.sendBidAcceptance(bid, group.rate)
                    self.NextPeriod.actionPlan.addBid(bid)
                else:
                    self.sendBidRejection(bid, group.rate)   
                    
            totaldemand = 0        
            #notify the counterparties of the terms on which they will consume power
            for bid in self.demandBidList:
                if bid.accepted:
                    totaldemand += bid.amount
                    self.sendBidAcceptance(bid, group.rate)
                    self.NextPeriod.actionPlan.addConsumption(bid)
                else:
                    self.sendBidRejection(bid, group.rate)
                    
            
            totalreserve = 0
            for bid in self.reserveBidList:
                if totalreserve < (maxLoad - totaldemand):
                    totalreserve += bid.amount
                    if totalreserve > (maxLoad - totaldemand):
                        #we have enough reserves, accept partial
                        bid.accepted = True
                        bid.modified = True
                        bid.amount = bid.amount - (maxLoad - totaldemand - totalreserve)
                    else:
                        bid.accepted = True
                else: 
                    bid.accepted = False
                    
            for bid in self.reserveBidList:
                if bid.accepted:
                    self.sendBidAcceptance(bid,group.rate)
                    self.NextPeriod.actionPlan.addBid(bid)
                else:
                    self.sendBidRejection(bid,group.rate)
                    
            self.bidstate.reserveonly()
            #now look at the revised bids
            
                                   
            #announce rates for next period
            for cust in group.customers:
                self.announceRate(cust,group.rate,self.NextPeriod.startTime)
                        
        self.NextPeriod.actionPlan.printInfo(0)
                
    def sendDR(self,target,type,duration):
        mesdict = {"message_subject" : "DR_event",
                   "message_sender" : self.name,
                   "message_target" : target,
                   "event_id" : random.getrandbits(32),
                   "event_duration": duration,
                   "event_type" : type
                    }
        message = json.dumps(mesdict)
        self.vip.pubsub.publish("pubsub","demandresponse",{},message)
    
    '''scheduled initially in init, the advancePeriod() function makes the period for
    which we were planning into the period whose plan we are carrying out at the times
    specified in the period objects. it schedules another call to itself each time and 
    also runs the enactPlan() function to actuate the planned actions for the new
    planning period '''    
    def advancePeriod(self):
        self.bidstate.acceptnone()
        #make next period the current period and create new object for next period
        self.CurrentPeriod = self.NextPeriod
        self.NextPeriod = control.Period(self.CurrentPeriod.periodNumber+1,self.CurrentPeriod.endTime,self.CurrentPeriod.endTime + timedelta(seconds = settings.ST_PLAN_INTERVAL),self.name)
        
        if settings.DEBUGGING_LEVEL >= 1:
            print("+*++*+++*++*+*++*+++*++*+*++*+++*++*+*++*+++*++*+*++*+++*++*+*++*+++*++*\nUTILITY AGENT {me} moving into new period:".format(me = self.name))
            self.CurrentPeriod.printInfo(0)
        
        #call enactPlan
        self.enactPlan()
                
        #schedule next advancePeriod call
        self.core.schedule(self.NextPeriod.startTime,self.advancePeriod)
        
                    
    '''responsible for enacting the plan which has been defined for a planning period'''
    def enactPlan(self):
        #which resources are being used during this period? keep track with this list
        involvedResources = []
        #change setpoints
        if self.CurrentPeriod.actionPlan:
            if settings.DEBUGGING_LEVEL >= 2:
                print("UTILITY {me} IS ENACTING ITS PLAN FOR PERIOD {per}".format(me = self.name, per = self.CurrentPeriod.periodNumber))
                
            for bid in self.CurrentPeriod.actionPlan.ownBids:
                res = listparse.lookUpByName(bid.resourceName,self.Resources)
                if res is not None:
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
                            res.DischargeChannel.connectWithSet(bid.amount,0)
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("Connecting resource {rname} with setpoint: {amt}".format(rname = res.name, amt = bid.amount))
                        elif bid.servie == "reserve":
                            #res.connectSourceSoft("Preg",.1)
                            res.DischargeChannel.connectWithSet(bid.amount, -.2)
                            if settings.DEBUGGING_LEVEL >= 2:
                                print("Committed resource {rname} as a reserve with setpoint: {amt}".format(rname = res.name, amt = bid.amount))
            #disconnect resources that aren't being used anymore
            for res in self.Resources:
                if res not in involvedResources:
                    if res.connected == True:
                        #res.disconnectSourceSoft()
                        res.DischargeChannel.disconnect()
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("Resource {rname} no longer required and is being disconnected".format(rname = res.name))
            
            
            
    
    '''monitor for and remediate fault conditions'''
    @Core.periodic(settings.FAULT_DETECTION_INTERVAL)
    def faultManager(self):
        nominal = True
        for group in self.groupList:
        #look for line-ground faults
            for node in group.membership:
                total = node.sumCurrents()
                if abs(total) > .1:
                    #there is a mismatch and probably a line-ground fault
                    node.isolateNode()
                    node.groundfault = True
                    group.groundfault = True
                    nominal = False
                    if settings.DEBUGGING_LEVEL >= 1:
                        if settings.DEBUGGING_LEVEL >= 2:
                            print("unaccounted current of {tot}".format(tot = total))
                        print("Probable line-ground Fault at Node {nod} belonging to {grp}\n  Isolating node.".format(nod = node.name, grp = group.name))
                
                        
                #look for brownouts
                for node in self.nodes:
                    voltage = node.getVoltage
                    if voltage < settings.VOLTAGE_LOW_EMERGENCY_THRESHOLD:
                        node.voltageLow = True
                        group.voltageLow = True
                        nominal = False
                        if settings.DEBUGGING_LEVEL >= 1:
                            print("!{me} detected emergency low voltage at node {nod} belonging to {grp}".format(me = self.name, nod = node.name, grp = group.name))
                    else:
                        node.voltageLow = False
            
            #detect relay failures  MAYBE
            
        if nominal:
            if settings.DEBUGGING_LEVEL >= 2:
                print("No faults detected by {me}!".format(me = self.name))
            
    
    ''' secondary voltage control loop to fix sagging voltage due to droop control''' 
    @Core.periodic(settings.SECONDARY_VOLTAGE_INTERVAL)       
    def correctVoltage(self):
        for group in self.groupList:
            avgVoltage = group.getAvgVoltage()
            if avgVoltage < settings.VOLTAGE_BAND_LOWER or avgVoltage > settings.VOLTAGE_BAND_UPPER:
                #only use our own resources
                pass
            
    def sendBidAcceptance(self,bid,rate):
        mesdict = {}
        mesdict["message_subject"] = "bid_acceptance"
        mesdict["message_target"] = bid.counterparty
        mesdict["message_sender"] = self.name
        
        mesdict["amount"] = bid.amount
        if bid.__class__.__name__ == "SupplyBid":
            mesdict["side"] = "supply"
            mesdict["service"] = bid.service
        elif bid.__class__.__name__ == "DemandBid":
            mesdict["side"] = "demand"
        else:
            mesdict["side"] = "unspecified"
            
        mesdict["rate"] = rate        
        mesdict["period"] = bid.period
        mesdict["uid"] = bid.uid
        
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY AGENT {me} sending bid acceptance to {them} for {uid}".format(me = self.name, them = bid.counterparty, uid = bid.uid))
        
        mess = json.dumps(mesdict)
        self.vip.pubsub.publish(peer = "pubsub",topic = "energymarket",headers = {}, message = mess)
        
    def sendBidRejection(self,bid,rate):
        mesdict = {}
        mesdict["message_subject"] = "bid_rejection"
        mesdict["message_target"] = bid.counterparty
        mesdict["message_sender"] = self.name
        
        mesdict["amount"] = bid.amount
        mesdict["rate"] = rate        
        if bid.__class__.__name__ == "SupplyBid":
            mesdict["side"] = "supply"
            mesdict["service"] = "service"
        elif bid.__class__.__name__ == "DemandBid":
            mesdict["side"] = "demand"
        else:
            mesdict["side"] = "unspecified"
        mesdict["period"] = bid.period
        mesdict["uid"] = bid.uid
        
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY AGENT {me} sending bid rejection to {them} for {uid}".format(me = self.name, them = bid.counterparty, uid = bid.uid))
        
        mess = json.dumps(mesdict)
        self.vip.pubsub.publish(peer = "pubsub",topic = "energymarket",headers = {}, message = mess)
    
    '''solicit participation in DR scheme from all customers who are not
    currently participants'''
    @Core.periodic(settings.DR_SOLICITATION_INTERVAL)
    def DREnrollment(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("\nUTILITY {me} TRYING TO ENROLL CUSTOMERS IN A DR SCHEME".format(me = self.name))
        for entry in self.customers:
            if entry.DRenrollee == False:
                self.solicitDREnrollment(entry.name)
    
    '''broadcast message in search of new customers'''
    @Core.periodic(settings.CUSTOMER_SOLICITATION_INTERVAL)
    def discoverCustomers(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("\nUTILITY {me} TRYING TO FIND CUSTOMERS".format(me = self.name))
        mesdict = self.standardCustomerEnrollment
        mesdict["message_sender"] = self.name
        message = json.dumps(mesdict)
        self.vip.pubsub.publish(peer = "pubsub", topic = "customerservice", headers = {}, message = message)
        
        if settings.DEBUGGING_LEVEL >= 1:
            print(message)
            
    
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
        #print("MAX getting called for {group}".format(group = group.name))
        total = 0
        #print(group.customers)
        for load in group.customers:
            total += load.maxDraw
            #print("adding {load} to max load".format(load = load.maxDraw))
        return total
    
    ''' assume that power consumption won't change much between one short term planning
    period and the next'''
    def getExpectedGroupLoad(self,group):
        #print("EXP getting called for {group}".format(group = group.name))
        total = 0
        #print(group.customers)
        for load in group.customers:
            total += load.getPower()
            #print("adding {load} to expected load".format(load = load.getPower()))
        return total
    
    '''update agent's knowledge of the current grid topology'''
    def getTopology(self):
        self.rebuildConnMatrix()
        subs = graph.findDisjointSubgraphs(self.connMatrix)
        if len(subs) >= 1:
            del self.groupList[:]
            for i in range(1,len(subs)+1):
                #create a new group class for each disjoint subgraph
                self.groupList.append(groups.Group("group{i}".format(i = i),[],[],[]))
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
                    cGroup.customers.extend(cNode.customers)
                    
        else:
            print("got a weird number of disjoint subgraphs in utilityagent.getTopology()")
        return subs
    
    '''builds the connectivity matrix for the grid's infrastructure'''
    def rebuildConnMatrix(self):
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY {me} REBUILDING CONNECTIVITY MATRIX".format(me = self.name))
        
        #what is the state of the tags supposed to be?
        infState = self.getLocalPreferred(self.infrastructureTags,5.1)
        
        #is main bus connected to BRANCH1.BUS1?
        if infState["BRANCH_1_BUS_1_PROXIMAL_User"]:
            self.connMatrix[0][1] = 1
            self.connMatrix[1][0] = 1
        else:
            self.connMatrix[0][1] = 0
            self.connMatrix[1][0] = 0
        
        #is main bus connected to BRANCH2.BUS1?
        if infState["BRANCH_1_BUS_2_PROXIMAL_User"]:
            self.connMatrix[0][2] = 1
            self.connMatrix[2][0] = 1
        else:
            self.connMatrix[0][2] = 0
            self.connMatrix[2][0] = 0
        
        #is BRANCH1.BUS1 connected to BRANCH2.BUS1
        if infState["BRANCH_1_BUS_1_DISTAL_User"] and infState["BRANCH_2_BUS_1_DISTAL_User"] and infState["INTERCONNECT_1_User"]:
            self.connMatrix[1][3] = 1
            self.connMatrix[3][1] = 1
        else:
            self.connMatrix[1][3] = 0
            self.connMatrix[3][1] = 0
            
        #is BRANCH1.BUS1 connected to BRANCH1.BUS2
        if infState["BRANCH_1_BUS_2_PROXIMAL_User"] and infState["BRANCH_1_BUS_1_DISTAL_User"]:
            self.connMatrix[1][2] = 1
            self.connMatrix[2][1] = 1
        else:
            self.connMatrix[1][2] = 0
            self.connMatrix[2][1] = 0
            
        #is BRANCH2.BUS1 connected to BRANCH2.BUS2
        if infState["BRANCH_2_BUS_2_PROXIMAL_User"] and infState["BRANCH_2_BUS_1_DISTAL_User"]:
            self.connMatrix[4][3] = 1
            self.connMatrix[3][4] = 1
        else:
            self.connMatrix[4][3] = 0
            self.connMatrix[3][4] = 0
        
        #is BRANCH2.BUS2 connected to BRANCH1.BUS2
        if infState["BRANCH_1_BUS_2_DISTAL_User"] and infState["BRANCH_2_BUS_2_DISTAL_User"] and infState["INTERCONNECT_2_User"]:
            self.connMatrix[2][4] = 1
            self.connMatrix[4][2] = 1
        else:
            self.connMatrix[2][4] = 0
            self.connMatrix[4][2] = 0
            
        #is BRANCH2.BUS1 connected to BRANCH1.BUS2?
        if infState["BRANCH_2_BUS_1_DISTAL_User"] and infState["BRANCH_1_BUS_2_PROXIMAL_User"] and infState["INTERCONNECT_1_User"]:
            self.connMatrix[2][3] = 1
            self.connMatrix[3][2] = 1
        else:
            self.connMatrix[2][3] = 0
            self.connMatrix[3][2] = 0
            
        #is BRANCH1.BUS1 connected to BRANCH2.BUS2?
        if infState["BRANCH_2_BUS_2_PROXIMAL_User"] and infState["BRANCH_1_BUS_1_DISTAL_User"] and infState["INTERCONNECT_1_User"]:
            self.connMatrix[1][4] = 1
            self.connMatrix[4][1] = 1
        else:
            self.connMatrix[1][4] = 0
            self.connMatrix[4][1] = 0
        
        #we should do more to validate this in case there is a fault...
        #does current through branch match bus voltage differential?
        
        #is there current at all?
        if settings.DEBUGGING_LEVEL >= 2:
            print("UTILITY {me} HAS FINISHED REBUILDING CONNECTIVITY MATRIX".format(me = self.name))
    
    def marketfeed(self, peer, sender, bus, topic, headers, message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get("message_subject",None)
        messageTarget = mesdict.get("message_target",None)
        messageSender = mesdict.get("message_sender",None)        
        
        if listparse.isRecipient(messageTarget,self.name):            
            if settings.DEBUGGING_LEVEL >= 2:
                print("\nUTILITY {me} RECEIVED AN ENERGYMARKET MESSAGE: {type}".format(me = self.name, type = messageSubject))
            if messageSubject == "bid_response":
                side = mesdict.get("side",None)
                rate =  mesdict.get("rate",None)
                duration = mesdict.get("duration",None)
                amount = mesdict.get("amount",None)
                period = mesdict.get("period",None)
                uid = mesdict.get("uid",None)
                resourceName = mesdict.get("resource",None)
                
                if side == "supply":
                    service = mesdict.get("service",None)
                    newbid = financial.SupplyBid(resourceName,service,amount,rate,messageSender,period,uid)
                    if service == "power":
                        self.supplyBidList.append(newbid)
                    elif service == "reserve":                  
                        self.reserveBidList.append(newbid)
                    
                elif side == "demand":
                    newbid = financial.DemandBid(amount,rate,messageSender,period,uid)
                    self.demandBidList.append(newbid)
                
                if settings.DEBUGGING_LEVEL >= 1:
                    print(message)
                    print("UTILITY {me} RECEIVED A {side} BID#{id} FROM {them}".format(me = self.name, side = side,id = uid, them = messageSender ))
                    if settings.DEBUGGING_LEVEL >= 3:
                        newbid.printInfo(0)
                
                
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
                        custobject = listparse.lookUpByName(messageSender,self.customers)
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
                            

    
    '''prints information about the utility and its assets'''
    def printInfo(self,verbosity):
        print("\n************************************************************************")
        print("~~SUMMARY OF UTILITY KNOWLEDGE~~")
        print("UTILITY NAME: {name}".format(name = self.name))
        
        print("--LIST ALL {n} UTILITY OWNED RESOURCES------".format(n = len(self.Resources)))
        for res in self.Resources:
            res.printInfo(1)
        print("--END RESOURCES LIST------------------------")
        print("--LIST ALL {n} CUSTOMERS----------------".format(n=len(self.customers)))
        for cust in self.customers:
            print("---ACCOUNT BALANCE FOR {them}: {bal} Credits".format(them = cust.name, bal = cust.customerAccount.accountBalance))
            cust.printInfo(1)
        print("--END CUSTOMER LIST---------------------")
        if verbosity > 1:
            print("--LIST ALL {n} DR PARTICIPANTS----------".format(n = len(self.DRparticipants)))
            for part in self.DRparticipants:
                part.printInfo(1)
            print("--END DR PARTICIPANTS LIST--------------")
            print("--LIST ALL {n} GROUPS------------------".format(n = len(self.groupList)))
            for group in self.groupList:
                group.printInfo(1)
            print("--END GROUPS LIST----------------------")
        print("~~~END UTILITY SUMMARY~~~~~~")
        print("*************************************************************************")
    
    
    '''get tag value by name, but use the tag client only if the locally cached
    value is too old, as defined in seconds by threshold'''
    def getLocalPreferred(self,tags,threshold, plc = "user"):
        reqlist = []
        outdict = {}
        indict = {}
        
        for tag in tags:
            try:
                #check cache to see if the tag is fresher than the threshold
                val, time = self.tagCache.get(tag,[None,None])
                #how much time has passed since the tag was last read from the server?
                diff = datetime.now()-time
                #convert to seconds
                et = diff.total_seconds()                
            except Exception:
                val = None
                et = threshold
                
            #if it's too old, add it to the list to be requested from the server    
            if et > threshold or val is None:
                reqlist.append(tag)
            #otherwise, add it to the output
            else:
                outdict[tag] = val
                
        #if there are any tags to be read from the server get them all at once
        if reqlist:
            indict = tagClient.readTags(reqlist,plc)
            if len(indict) == 1:
                outdict[reqlist[0]] = indict[reqlist[0]]
            else:
                for updtag in indict:
                    #then update the cache
                    self.tagCache[updtag] = (indict[updtag], datetime.now())
                    #then add to the output
                    outdict[updtag] = indict[updtag]
            
            #output should be an atom if possible (i.e. the request was for 1 tag
            if len(outdict) == 1:
                return outdict[tag]
            else:
                return outdict
    
    '''get tag by name from tag server'''
    def getTag(self,tag, plc = "user"):
         return tagClient.readTags([tag],plc)[tag]
    
    '''close an infrastructure relay. note that the logic is backward. this is
    because I used the NC connection of the SPDT relays for these'''
    def closeInfRelay(self,rname):
        tagClient.writeTags([rname],[False])
        
    '''open an infrastructure relay. note that the logic is backward. this is
    because I used the NC connection of the SPDT relays for these'''
    def openInfRelay(self,rname):
        tagClient.writeTags([rname],[True])
        
class BidState(object):
    def __init__(self):
        self.reservepolicy = False
        self.supplypolicy = False
        self.demandpolicy = False
        
        self.ignorelist = []
        
    def acceptall(self):
        self.reservepolicy = True
        self.supplypolicy = True
        self.demandpolicy = True
        
    def reserveonly(self):
        self.reservepolicy = True
        self.supplypolicy = False
        self.demandpolicy = False
        
    def acceptnone(self):
        self.reservepolicy = False
        self.supplypolicy = False
        self.demandpolicy = False
        
    def addtoignore(self,name):
        self.ignorelist.append(name)
    
        
def main(argv = sys.argv):
    try:
        utils.vip_main(UtilityAgent)
    except Exception as e:
        _log.exception('unhandled exception')
        
if __name__ == '__main__':
    sys.exit(main())
    
