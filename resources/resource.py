from DCMGClasses.resources.math import interpolation
#from DCMGClasses.CIP import wrapper
from DCMGClasses.CIP import tagClient

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
        
        
        DischargeChannel = Channel(dischargeChannel)
        
        
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
        self.DischargeChannel.connect(mode,setpoint)
    
    def disconnectSource(self):
        self.DischargeChannel.disconnect()
    

class Storage(Source):
    
    def __init__(self,owner,location,name,capCost,maxDischargePower,maxChargePower,capacity,chargeChannel,dischargeChannel,**kwargs):
        super(Storage,self).__init__(owner,location,name,capCost,maxDischargePower,dischargeChannel,**kwargs)
        self.chargePower = maxChargePower
        self.capacity = capacity
        self.chargeChannel = chargeChannel
        
        
        self.SOC = 0
        self.energy = 0
        
        ChargeChannel = Channel(chargeChannel)
        
                
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
        
    def getRegV(self):
        tagName = "SOURCE_{d}_RegVoltage".format(d = self.channelNumber)     
        #call to CIP wrapper
        #value = getTagValue(tagName)
        value = tagClient([tagName])
        return value   
        
    def getUnregV(self):
        tagName = "SOURCE_{d}_UnregVoltage".format(d = self.channelNumber)
        #value = wrapper.getTagValue(tagName)
        value = tagClient([tagName])
        return value
    
    def getRegI(self):
        tagName = "SOURCE_{d}_RegCurrent".format(d = self.channelNumber)
        #value = getTagValue(tagName)
        value = tagClient([tagName])
        return value
    
    def getUnregI(self):
        tagName = "SOURCE_{d}_UnregCurrent".format(d = self.channelNumber)
        #value = getTagValue(tagName)
        value = tagClient([tagName])
        return value
    
    '''connects the channel converter and puts it in one of several operating modes.
    Behaviors in each of these modes are governed by the PLC ladder code'''
    def connect(self,mode,setpoint):
        ch = self.channelNumber
        
        if mode == "Vreg":
            tag = "SOURCE_{d}_VoltageSetpoint_DUMMY".format(d = ch)
            tagClient.writeTags([tag],[0])
            tags = ["SOURCE_{d}_BATTERY_CHARGE_SElECT_DUMMY".format(d = ch),
                    "SOURCE_{d}_POWER_REG_SELECT_DUMMY".format(d = ch),
                    "SOURCCE_{d}_SWING_SOURCE_SELECT_DUMMY".format(d = ch)]
            tagClient.writeTags([tags],[False,False,True])
            tag = "SOURCE_{d}_DUMMY".format(d = ch)
            tagClient.writeTags([tag],[True])
            tag = "SOURCE_{d}_VoltageSetpoint_DUMMY".format(d = ch)
            tagClient.writeTags([tag],[setpoint])
        elif mode == "Preg":
            tag = "SOURCE_{d}_PowerSetpoint_DUMMY".format(d = ch)
            tagClient.writeTags([tag],[0])
            tags = ["SOURCE_{d}_BATTERY_CHARGE_SELECT_DUMMY".format(d = ch),
                    "SOURCE_{d}_POWER_REG_SELECT_DUMMY".format(d = ch),
                    "SOURCE_{d}_SWING_SOURCE_SELECT_DUMMY".format(d = ch)]
            tagClient.writeTags([tags],[False,True,False])
            tag = "SOURCE_{d}_DUMMY".format(d = ch)
            tagClient.writeTags([tag],[True])
            tag = "SOURCE_{d}_PowerSetpoint_DUMMY".format(d = ch)
            tagClient([tag],[setpoint])
        elif mode == "BattCharge":
            tags = ["SOURCE_{d}_PowerSetpoint_DUMMY".format(d = self.channelNumber),
                   "SOURCE_{d}_BATTERY_CHARGE_SELECT_DUMMY".format(d = self.channelNumber)]
            tagClient.writeTags([tags],[0,True])
            tag = "SOURCE_{d}_BatteryReqCharge_DUMMY".format(d = self.channelNumber)
            tagClient.writeTags([tag],[True])
            tag = "SOURCE_{d}_PowerSetpoint_DUMMY".format(d = self.channelNumber)
            tagClient.writeTags([tag],[setpoint])
        else:
            print("CHANNEL{ch} received a bad mode request: {mode}".format(ch = self.channelNumber,mode = mode))
    
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
        
        
        