from DCMGClasses.resources.math import interpolation
#from DCMGClasses.CIP import wrapper
from DCMGClasses.CIP import tagClient
from volttron.platform.vip.agent import Core

from datetime import datetime, timedelta

class Resource(object):
    
    def __init__(self,owner,location,name,capCost,**kwargs):
        self.owner = owner
        self.location = location
        self.capCost = capCost
        self.name = name
        
    def setOwner(self,newOwner):
        print("transferring ownership of {resource} from {owner} to {newowner}".format(resource = self, owner = self.owner, newowner = newOwner))
        self.owner = newOwner
        
    def printInfo(self):
        print("    **RESOURCE: {name} owned by {owner}\n        TYPE:{type}\n        LOCATION:{loc}".format(name = self.name, owner = self.owner, type = self.__class__.__name__, loc = self.location))

class Source(Resource):
    def __init__(self,owner,location,name,capCost,maxDischargePower,dischargeChannel,**kwargs):
        super(Source,self).__init__(owner,location,name,capCost)
        self.maxDischargePower = maxDischargePower
        self.dischargeChannel = dischargeChannel
        
        self.availDischargePower = 0
        
        self.connected = False
        
        self.DischargeChannel = Channel(dischargeChannel)
        
        
    def getInputUnregVoltage(self):
        voltage = self.DischargeChannel.getUnregV()
        return voltage
    
    def getOutputRegVoltage(self):
        voltage = self.DischargeChannel.getRegV()
        return voltage
        
    def getInputUnregCurrent(self):
        current = self.DischargeChannel.getUnregI()
        return current
        
    def getOutputUnregCurrent(self):
        current = self.DischargeChannel.getRegI()
        return current
    
    def connectSource(self,mode,setpoint):
        self.connected = self.DischargeChannel.connect(mode,setpoint)
        
    def connectSourceSoft(self,mode,setpoint):
        self.connected = self.DischargeChannel.connectSoft(mode,setpoint)
    
    def disconnectSource(self):
        self.connected = self.DischargeChannel.disconnect()
        
    def disconnectSourceSoft(self):
        self.connected = self.DischargeChannel.disconnectSoft()
    

class Storage(Source):
    
    def __init__(self,owner,location,name,capCost,maxDischargePower,maxChargePower,capacity,chargeChannel,dischargeChannel,**kwargs):
        super(Storage,self).__init__(owner,location,name,capCost,maxDischargePower,dischargeChannel,**kwargs)
        self.chargePower = maxChargePower
        self.capacity = capacity
        self.chargeChannel = chargeChannel
        
        
        self.SOC = 0
        self.energy = 0
        
        self.ChargeChannel = Channel(chargeChannel)
        
                
class LeadAcidBattery(Storage):
    SOCtable = [(0, 11.8),(.25, 12.0),(.5, 12.2),(.75, 12.4),(1, 12.7)]
    def __init__(self,owner,location,name,capCost,maxDischargePower,maxChargePower,capacity,chargeChannel,dischargeChannel,**kwargs):
        super(LeadAcidBattery,self).__init__(owner,location,name,capCost,maxDischargePower,maxChargePower,capacity,chargeChannel,dischargeChannel,**kwargs)
        self.SOC = self.getSOCfromOCV()
        
        self.cyclelife = 1000
        self.amortizationPeriod = 10
        
    def getSOC(self):
        #get SOC from PLC
        pass
    
    def getSOCfromOCV(self):
        #get battery voltage from PLC
        tagname = "SOURCE_{num}_REG_VOLTAGE".format(num = self.DischargeChannel.channelNumber)
        voltage = getTagValue(tagName)
        soc = interpolation.lininterp(self.SOCtable,voltage)
        return soc
    
    def charge(self,setpoint):
        self.chargeChannel.connect("BattCharge",setpoint)
        
class SolarPanel(Source):
    def __init__(self,owner,location,name,capCost,maxDischargePower,dischargeChannel,Voc,Vmpp,**kwargs):
        super(SolarPanel,self).__init__(owner,location,name,capCost,maxDischargePower,dischargeChannel,**kwargs)
        self.Voc = Voc
        self.Vmpp = Vmpp
        
        self.amortizationPeriod = 10
        
    def powerAvailable(self):
        pass
        
    
class Channel():
    def __init__(self,channelNumber):
        self.channelNumber = channelNumber
        
        self.connected = False
        
        
        #PLC tag names generated from channel number
        self.relayTag = "SOURCE_{d}_DUMMY".format(d = self.channelNumber)
        self.vSetpointTag = "SOURCE_{d}_VoltageSetpoint_DUMMY".format(d = self.channelNumber)
        self.pSetpointTag = "SOURCE_{d}_PowerSetpoint_DUMMY".format(d = self.channelNumber)
        self.swingSelectTag = "SOURCCE_{d}_SWING_SOURCE_SELECT_DUMMY".format(d = self.channelNumber)
        self.powerSelectTag = "SOURCE_{d}_POWER_REG_SELECT_DUMMY".format(d = self.channelNumber)
        self.battSelectTag = "SOURCE_{d}_BATTERY_CHARGE_SElECT_DUMMY".format(d = self.channelNumber)
        self.noLoadVoltageTag = "SOURCE_{d}_noLoadVoltage".format(d = self.channelNumber)
        self.droopCoeffTag = "SOURCE_{d}_droopCoeff".format(d = self.channelNumber)
        
        self.regVTag = "SOURCE_{d}_RegVoltage".format(d = self.channelNumber)
        self.unregVTag = "SOURCE_{d}_UnregVoltage".format(d = self.channelNumber)
        self.regItag =  "SOURCE_{d}_RegCurrent".format(d = self.channelNumber)
        self.unregItag = "SOURCE_{d}_UnregCurrent".format(d = self.channelNumber)
        
    def getRegV(self):
        tagName = self.regVTag     
        #call to CIP wrapper
        #value = getTagValue(tagName)
        value = tagClient([tagName])
        return value   
        
    def getUnregV(self):
        tagName = self.unregVTag
        #value = wrapper.getTagValue(tagName)
        value = tagClient([tagName])
        return value
    
    def getRegI(self):
        tagName = self.regItag
        #value = getTagValue(tagName)
        value = tagClient([tagName])
        return value
    
    def getUnregI(self):
        tagName = self.unregItag
        #value = getTagValue(tagName)
        value = tagClient([tagName])
        return value
    
    def disconnect(self):
        #disconnect power from the source
        tagClient.writeTags([self.relayTag],[False])
        #return setpoint to zero
        tagClient.writeTags([self.vSetpointTag],[0])
        tagClient.writeTags([self.pSetpointTag],[0])
        #read tag to confirm write success
        return tagClient.readTags([self.relayTag])
    
    def disconnectSoft(self,maxStep = .5):
        #ramp down power setpoint and disconnect when finished
        self.ramp(0,maxStep,True)
    
    def connectDroop(self,setpoint,noLoadVoltage = 12, refVoltage = 11.8):
        #set up parameters for droop control
        tags = [self.noLoadVoltageTag, self.pSetpointTag, self.droopCoeffTag]
        values = [noLoadVoltage, setpoint, setpoint/(noLoadVoltage - refVoltage)]
        tagClient.writeTags(tag,values)
        #close relay and connect source
        tagClient.writeTags([self.relayTag],[True])
        
        if tagClient.readTags([self.relayTag]):
            self.connected = True
            return True
        else:
            self.connected = False
            return False
    
    
    
    '''connects the channel converter and puts it in one of several operating modes.
    Behaviors in each of these modes are governed by the PLC ladder code'''
    def connect(self,mode,setpoint):
        ch = self.channelNumber
        
        if mode == "Vreg":
            tagClient.writeTags([self.vSetpointTag],[0])
            tags = [self.battSelectTag ,
                    self.powerSelectTag,
                    self.swingSelectTag]
            tagClient.writeTags([tags],[False,False,True])
            tagClient.writeTags([self.relayTag],[True])
            tagClient.writeTags([self.vSetpointTag],[setpoint])
        elif mode == "Preg":
            tagClient.writeTags([self.pSetpointTag],[0])
            tags = [self.battSelectTag ,
                    self.powerSelectTag,
                    self.swingSelectTag]
            tagClient.writeTags([tags],[False,True,False])
            tagClient.writeTags([self.relayTag],[True])
            tagClient([self.pSetpointTag],[setpoint])
        elif mode == "BattCharge":
            tags = [self.pSetpointTag,
                   self.battSelectTag]
            tagClient.writeTags([tags],[0,True])
            tag = "SOURCE_{d}_BatteryReqCharge_DUMMY".format(d = self.channelNumber)
            tagClient.writeTags([tag],[True])
            tagClient.writeTags([self.pSetpointTag],[setpoint])
        else:
            print("CHANNEL{ch} received a bad mode request: {mode}".format(ch = self.channelNumber,mode = mode))
        
        if tagClient.readTags([self.relayTag]):
            self.connected = True
            return True
        else:
            self.connected = False
            return False
    '''connects in one of the usual modes, but if it's a power regulating source
    it ramps up gradually to avoid exceeding swing source headroom'''
    def connectSoft(self,mode,setpoint):
        ch = self.channelNumber
        
        if mode == "Vreg":
            tagClient.writeTags([self.vSetpointTag],[0])
            tags = [self.battSelectTag ,
                    self.powerSelectTag,
                    self.swingSelectTag]
            tagClient.writeTags([tags],[False,False,True])
            tagClient.writeTags([self.relayTag],[True])
            tagClient.writeTags([self.vSetpointTag],[setpoint])
        elif mode == "Preg":
            tagClient.writeTags([self.pSetpointTag],[0])
            tags = [self.battSelectTag,
                    self.powerSelectTag,
                    self.swingSelectTag]
            tagClient.writeTags([tags],[False,True,False])
            tagClient.writeTags([self.relayTag],[True])
            self.ramp(setpoint)
        elif mode == "BattCharge":
            tags = [self.pSetpointTag,
                   self.battSelectTag]
            tagClient.writeTags([tags],[0,True])
            tag = "SOURCE_{d}_BatteryReqCharge_DUMMY".format(d = self.channelNumber)
            tagClient.writeTags([tag],[True])
            tagClient.writeTags([self.pSetpointTag],[setpoint])
        else:
            print("CHANNEL{ch} received a bad mode request: {mode}".format(ch = self.channelNumber,mode = mode))
            
        if tagClient.readTags([self.relayTag]):
            self.connected = True
            return True
        else:
            self.connected = False
            return False
    
    def ramp(self,setpoint,maxStep = .5,disconnectWhenFinished = False):
        tag = self.pSetpointTag
        currentSetpoint = tagClient.readTags([tag])
        diff = setpoint - currentSetpoint
        if diff > maxStep:
            currentSetpoint += maxStep
        elif diff < -maxStep:
            currentSetpoint -= maxStep
        else:
            currentSetpoint += diff
        tagClient.writeTags([tag],[currentSetpoint])
        
        if abs(diff) > .001:
            #schedule a callback, allowing some time for actuation
            sched = datetime.now() + timedelta(seconds = 1.5)
            Core.schedule(sched,self.ramp)
            print("{me} is scheduling another ramp call: {cs}".format(me = self.channelNumber, cs = currentSetpoint))
            if disconnectWhenFinished == True and setpoint == 0:
                print("ramp with disconnect completed, disconnecting {me}".format(me = self.channelNumber))
                self.disconnect()
        else:
            print("{me} is done ramping to {set}".format(me = self.name, set = setpoint))
        
    
def addResource(strlist,classlist,debug = False):
    def addOne(item,classlist):
        if type(item) is dict:
            resType = item.get("type",None)
            if resType == "solar":
                res = SolarPanel(**item)
            elif resType == "lead_acid_battery":
                res = LeadAcidBattery(**item)
            else:
                pass
            classlist.append(res)
        
    if type(strlist) is list:
        if len(strlist) > 1:
            if debug:
                print("list contains multiple resources")
            for item in strlist:
                if debug:
                    print("working on new element")
                addOne(item,classlist)                
        if len(strlist) == 1:
            if debug:
                print("list contains one resource")
            addOne(strlist[0],classlist)
    elif type(strlist) is dict:
        if debug:
            print("no list, just a single dict")
        addOne(strlist,classlist)
    if debug:
        print("here's how the classlist looks now: {cl}".format(cl = classlist))
        
        
        