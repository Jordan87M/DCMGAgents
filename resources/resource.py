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
        self.tagCache = {}
        
    def setOwner(self,newOwner):
        print("transferring ownership of {resource} from {owner} to {newowner}".format(resource = self, owner = self.owner, newowner = newOwner))
        self.owner = newOwner
        
    def printInfo(self, depth = 0):
        space = '    '
        print(spaces*depth + "**RESOURCE: {name} owned by {owner}\n        TYPE:{type}\n        LOCATION:{loc}".format(name = self.name, owner = self.owner, type = self.__class__.__name__, loc = self.location))

class Source(Resource):
    def __init__(self,owner,location,name,capCost,maxDischargePower,dischargeChannel,**kwargs):
        super(Source,self).__init__(owner,location,name,capCost)
        self.maxDischargePower = maxDischargePower
        self.dischargeChannel = dischargeChannel
        
        self.availDischargePower = 0
        
        self.connected = False
        
        self.DischargeChannel = Channel(dischargeChannel)
        
        #should only be nonzero if the resource is enrolled in frequency regulation
        self.FREG_power = 0
              
        
    def getInputUnregVoltage(self):
        voltage = self.DischargeChannel.getUnregV()
        return voltage
    
    def getOutputRegVoltage(self):
        voltage = self.DischargeChannel.getRegV()
        return voltage
        
    def getInputUnregCurrent(self):
        current = self.DischargeChannel.getUnregI()
        return current
        
    def getOutputRegCurrent(self):
        current = self.DischargeChannel.getRegI()
        return current
    
    def getOutputUnegPower(self):
        current = self.DischargeChannel.getUnregI()
        voltage = self.DischargeChannel.getUnregV()
        return current*voltage
    
    def getOutputRegPower(self):
        current = self.DischargeChannel.getRegI()
        voltage = self.DischargeChannel.getRegV()
        return current*voltage
    
    def connectSource(self,mode,setpoint):
        self.connected = self.DischargeChannel.connect(mode,setpoint)
        
    def connectSourceSoft(self,mode,setpoint):
        self.connected = self.DischargeChannel.connectSoft(mode,setpoint)
    
    def disconnectSource(self):
        self.connected = self.DischargeChannel.disconnect()
        
    def disconnectSourceSoft(self):
        self.connected = self.DischargeChannel.disconnectSoft()
    
    def printInfo(self, depth = 0, verbosity = 0):
        spaces = '    '
        print(spaces*depth + "**RESOURCE: {name} owned by {owner}\n        TYPE:{type}\n        LOCATION:{loc}".format(name = self.name, owner = self.owner, type = self.__class__.__name__, loc = self.location))
        if verbosity == 1:
            print(spaces*depth + "CURRENT OPERATING INFO:")
            print(spaces*depth + "VUNREG: {vu}  IUNREG: {iu}".format(vu = self.getInputUnregVoltage(), iu = self.getInputUnregCurrent()))
            print(spaces*depth + "VREG: {vr}  IREG: {ir}".format(vr = self.getOutputRegVoltage(), ir = self.getOutputRegCurrent()))

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
        
        self.FREG_power = .2*maxChargePower
        
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
        
        #droop stuff
        self.noLoadVoltage = 12
        self.refVoltage = 11.8
        self.setpoint = 0
        
        
        #PLC tag names generated from channel number
        #tags for writing
        self.relayTag = "SOURCE_{d}_User".format(d = self.channelNumber)
        self.pSetpointTag = "SOURCE_{d}_psetpoint".format(d = self.channelNumber)
        self.battSelectTag = "SOURCE_{d}_BATTERY_CHARGE_SElECT".format(d = self.channelNumber)
        self.battReqChargeTag = "SOURCE_{d}_BatteryReqCharge".format(d = self.channelNumber)
        self.droopSelectTag = "SOURCE_{d}_DROOP_SELECT".format(d = self.channelNumber)
        self.noLoadVoltageTag = "SOURCE_{d}_noLoadVoltage".format(d = self.channelNumber)
        self.droopCoeffTag = "SOURCE_{d}_droopCoeff".format(d = self.channelNumber)
        
        #deprecated tags for writing
        self.vSetpointTag = "SOURCE_{d}_VoltageSetpoint".format(d = self.channelNumber)
        self.swingSelectTag = "SOURCCE_{d}_SWING_SOURCE_SELECT".format(d = self.channelNumber)
        self.powerSelectTag = "SOURCE_{d}_POWER_REG_SELECT".format(d = self.channelNumber)

        #tags for reading
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
    
    '''low level method. only opens the relay'''
    def disconnect(self):
        #disconnect power from the source
        tagClient.writeTags([self.relayTag],[False])
        #read tag to confirm write success
        return tagClient.readTags([self.relayTag])
    
    def disconnectSoft(self):
        #change setpoint to zero
        tagClient.writeTags([self.pSetpointTag],[0])
        #callback and keep calling back until the current is almost zero
        now = datetime.now()
        Core.schedule(now + timedelta(seconds = 1),self.waitForSettle)
    
    #when the current drops to zero, disconnect the source    
    def waitForSettle(self):
        current = tagClient.readTag([self.regItag])
        if abs(current) < .005:
            self.connected = self.disconnect()
        else:
            now = datetime.now()
            Core.schedule(now + timedelta(seconds = 1),self.waitForSettle)
    
    '''low level method to be called by other methods. only closes the relay'''
    def connect(self):
        tagClient.writeTags([self.relayTag],[True])
        #read tag to confirm write success
        self.connected = tagClient.readTags([self.relayTag])
        return self.connected
    
    '''calculates droop coefficient based on setpoint and writes to PLC before connecting
    the resource. includes an optional voltage offset argument to be used with reserves'''    
    def connectWithSet(self,setpoint,voffset = 0):
        self.setpoint = setpoint
        #set up parameters for droop control
        tags = [self.noLoadVoltageTag, self.pSetpointTag, self.droopCoeffTag, self.droopSelectTag]
        values = [self.noLoadVoltage + voffset, setpoint, self.setpoint/(self.noLoadVoltage - self.refVoltage), True]
        tagClient.writeTags(tags,values)
        #close relay and connect source
        self.connected = self.connect()
        return self.connected
    
    '''changes the droop coefficient by updating the power target at the reference voltage
     and writes it to the PLC. to be used on sources that are already connected'''
    def changeSetpoint(self,newPower):
        self.setpoint = newPower
        droopCoeff = self.setpoint/(self.noLoadVoltage - self.refVoltage)
        tagClient.writeTags([self.droopCoeffTag],[droopCoeff])
    
    '''changes the droop coefficient by updating the power target at the reference voltage
    and writes it to the PLC. also takes a voltage offset argument. to be used with reserve
    sources that are already connected'''
    def changeReserve(self,newPower,voffset):
        self.setpoint = newPower
        droopCoeff = self.setpoint/(self.noLoadVoltage - self.refVoltage)
        tagClient.writeTags([self.droopCoeffTag, self.noLoadVoltageTag],[droopCoeff, self.noLoadVoltage + voffset])
    
    '''creates a voltage offset to the V-P curve corresponding to the addition of a fixed
    amount of power, poffset, at every voltage.'''        
    def setPowerOffset(self,poffset):
        droopCoeff = self.setpoint/(self.noLoadVoltage - self.refVoltage)
        voffset = poffset/droopCoeff
        self.setVoltageOffset(voffset)
        
    '''adds a voltage offset corresponding to an increase in the power offset of deltapoffset'''    
    def addPowerOffset(self,deltapoffset):
        droopCoeff = self.setpoint/(self.noLoadVoltage - self.refVoltage)
        deltavoffset = deltapoffset/droopCoeff
        self.addVoltageOffset(deltavoffset)
    
    '''creates a voltage offset to V-P curve. can be used to create reserve sources
    that are only deployed when needed'''    
    def setVoltageOffset(self,voffset):
        tagClient.writeTags([self.noLoadVoltageTag],[self.noLoadVoltage + voffset])
    
    '''adds to the voltage offset an amount deltavoffset. can be used to implement
    a secondary control loop to correct voltage'''
    def addVoltageOffset(self,deltavoffset):
        voffset = tagClient.readTags([self.noLoadVoltage])
        voffset += deltavoffset
        tagClient.writeTags([self.noLoadVoltage],[voffset])
        
    #deprecated functions below
    '''connects the channel converter and puts it in one of several operating modes.
    Behaviors in each of these modes are governed by the PLC ladder code'''
    def connectMode(self,mode,setpoint):
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
            tag = "SOURCE_{d}_BatteryReqCharge".format(d = self.channelNumber)
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
            tag = "SOURCE_{d}_BatteryReqCharge".format(d = self.channelNumber)
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
        
    def disconnectSoft(self,maxStep = .5):
        #ramp down power setpoint and disconnect when finished
        self.ramp(0,maxStep,True)
        
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
        
    
def makeResource(strlist,classlist,debug = False):
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
        
        
        